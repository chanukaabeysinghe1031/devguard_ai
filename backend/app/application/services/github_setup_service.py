"""GitHub App installation and repository connection management (ADR-005).

Handles the signed setup ``state`` round-trip, the org-scoped installation
registry, and the per-project repository connection with its automation flags.
No secret material is returned by any method here.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.webhook_delivery_service import WebhookDeliveryService
from app.core.config import Settings
from app.domain.enums import GitHubInstallationStatus
from app.domain.exceptions.business import (
    ConflictError,
    ResourceNotFoundError,
    ValidationBusinessError,
)
from app.domain.exceptions.integration import GitHubProviderError, IntegrationDisabledError
from app.domain.interfaces.github_provider import GitHubProvider
from app.domain.services.github_event_filters import (
    DEFAULT_FAILURE_CONCLUSIONS,
    DEFAULT_SEVERITY_RULES,
)
from app.infrastructure.database.models.github_installation import GitHubInstallation
from app.infrastructure.database.models.github_repository_connection import (
    GitHubRepositoryConnection,
)
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery
from app.infrastructure.security.integration_crypto import (
    decrypt_state,
    encrypt_state,
    state_expiry,
)
from app.schemas.integration import (
    BranchFilters,
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionUpdateRequest,
    GitHubInstallationListResponse,
    GitHubInstallationResponse,
    GitHubRepositoryListResponse,
    GitHubRepositoryResponse,
    GitHubStatusResponse,
    GitHubWorkflowListResponse,
    GitHubWorkflowResponse,
    InstallUrlResponse,
    ProjectIntegrationListResponse,
    ProjectIntegrationSummary,
    SetupCompleteResponse,
    WebhookActivityItem,
    WebhookActivityListResponse,
    WorkflowFilters,
)

logger = structlog.get_logger(__name__)

GITHUB_PROVIDER_KEY = "github_actions"

# Providers shown in the UI but not connectable in Phase 5B (ADR-005 §10).
_DEFERRED_PROVIDERS: tuple[tuple[str, str], ...] = (
    ("gitlab", "GitLab CI"),
    ("jenkins", "Jenkins"),
    ("azure_devops", "Azure DevOps"),
    ("terraform_cloud", "Terraform Cloud"),
)


class GitHubSetupService:
    """Installation and connection lifecycle for the GitHub integration."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        provider: GitHubProvider,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider

    # ------------------------------------------------------------------
    # Status and setup
    # ------------------------------------------------------------------
    async def status(self, *, organization_id: UUID) -> GitHubStatusResponse:
        installation_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(GitHubInstallation)
                .where(GitHubInstallation.organization_id == organization_id)
            )
            or 0
        )
        connection_count = int(
            await self._session.scalar(
                select(func.count())
                .select_from(GitHubRepositoryConnection)
                .where(
                    GitHubRepositoryConnection.organization_id == organization_id,
                    GitHubRepositoryConnection.disconnected_at.is_(None),
                )
            )
            or 0
        )
        app_configured = (
            bool(
                self._settings.github_app_id
                and (
                    self._settings.github_app_private_key_path
                    or self._settings.github_app_private_key_pem
                )
            )
            or self._settings.github_provider == "fake"
        )
        return GitHubStatusResponse(
            enabled=self._settings.github_app_enabled,
            provider=self._settings.github_provider,
            app_configured=app_configured,
            webhook_configured=bool(self._settings.github_webhook_secret),
            app_slug=self._settings.github_app_slug or None,
            installation_count=installation_count,
            connection_count=connection_count,
        )

    def _require_enabled(self) -> None:
        if not self._settings.github_app_enabled:
            raise IntegrationDisabledError()

    async def build_install_url(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        project_id: UUID,
    ) -> InstallUrlResponse:
        self._require_enabled()
        await self._load_project(organization_id, project_id)

        expires_at = state_expiry(ttl_seconds=self._settings.github_setup_state_ttl_seconds)
        state = encrypt_state(
            {
                "organization_id": str(organization_id),
                "project_id": str(project_id),
                "user_id": str(user_id),
                "nonce": secrets.token_urlsafe(16),
                "expires_at": expires_at,
            },
            settings=self._settings,
        )
        slug = (self._settings.github_app_slug or "").strip()
        base = self._settings.github_app_install_base_url.rstrip("/")
        install_url = f"{base}/{slug}/installations/new?state={state}" if slug else ""
        if not install_url:
            raise IntegrationDisabledError("GITHUB_APP_SLUG is not configured.")
        return InstallUrlResponse(
            install_url=install_url,
            state=state,
            expires_at=datetime.fromisoformat(expires_at),
            project_id=project_id,
        )

    async def complete_setup(
        self,
        *,
        organization_id: UUID,
        installation_id: int,
        state: str,
    ) -> SetupCompleteResponse:
        self._require_enabled()
        payload = decrypt_state(
            state,
            settings=self._settings,
            max_age_seconds=self._settings.github_setup_state_ttl_seconds,
        )
        state_org = payload.get("organization_id")
        if str(state_org) != str(organization_id):
            raise ValidationBusinessError(
                "Setup state does not belong to this organization.",
                error_code="INTEGRATION_STATE_MISMATCH",
            )

        info = await self._provider.get_installation(installation_id)
        existing = await self._session.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.github_installation_id == installation_id
            )
        )
        if existing is not None and existing.organization_id != organization_id:
            raise ConflictError(
                "This GitHub installation is already linked to another organization.",
                error_code="INSTALLATION_ALREADY_LINKED",
            )

        now = datetime.now(UTC)
        if existing is None:
            existing = GitHubInstallation(
                organization_id=organization_id,
                github_installation_id=installation_id,
                installed_at=info.created_at or now,
            )
            self._session.add(existing)

        existing.github_account_id = info.account_id
        existing.github_account_login = info.account_login or str(installation_id)
        existing.account_type = info.account_type
        existing.status = GitHubInstallationStatus.ACTIVE.value
        existing.permissions_json = dict(info.permissions) if info.permissions else None
        existing.repository_selection = info.repository_selection
        existing.suspended_at = None
        await self._session.flush()

        project_id = payload.get("project_id")
        logger.info(
            "github_installation_registered",
            organization_id=str(organization_id),
            github_installation_id=installation_id,
        )
        return SetupCompleteResponse(
            installation=self._installation_response(existing),
            project_id=UUID(str(project_id)) if project_id else None,
            redirect_url=self._settings.github_setup_redirect_url or None,
        )

    async def list_installations(
        self,
        *,
        organization_id: UUID,
    ) -> GitHubInstallationListResponse:
        stmt = (
            select(GitHubInstallation)
            .where(GitHubInstallation.organization_id == organization_id)
            .order_by(GitHubInstallation.created_at.desc())
        )
        rows = list((await self._session.scalars(stmt)).all())
        return GitHubInstallationListResponse(
            items=[self._installation_response(row) for row in rows]
        )

    async def list_repositories(
        self,
        *,
        organization_id: UUID,
        installation_row_id: UUID,
    ) -> GitHubRepositoryListResponse:
        self._require_enabled()
        installation = await self._load_installation(organization_id, installation_row_id)
        repositories = await self._provider.list_installation_repositories(
            installation.github_installation_id
        )
        connected = {
            row.github_repository_id: row.project_id
            for row in (
                await self._session.scalars(
                    select(GitHubRepositoryConnection).where(
                        GitHubRepositoryConnection.organization_id == organization_id,
                        GitHubRepositoryConnection.disconnected_at.is_(None),
                    )
                )
            ).all()
        }
        return GitHubRepositoryListResponse(
            items=[
                GitHubRepositoryResponse(
                    github_repository_id=repo.repository_id,
                    full_name=repo.full_name,
                    default_branch=repo.default_branch,
                    html_url=repo.html_url,
                    private=repo.private,
                    connected_project_id=connected.get(repo.repository_id),
                )
                for repo in repositories
            ]
        )

    # ------------------------------------------------------------------
    # Project connections
    # ------------------------------------------------------------------
    async def list_project_integrations(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> ProjectIntegrationListResponse:
        await self._load_project(organization_id, project_id)
        connection = await self._find_connection(organization_id, project_id)
        github_status = "not_connected"
        if connection is not None:
            github_status = "paused" if connection.is_paused else "connected"
        items = [
            ProjectIntegrationSummary(
                provider=GITHUB_PROVIDER_KEY,
                display_name="GitHub Actions",
                status=github_status,
                available=self._settings.github_app_enabled,
                connection=self._connection_response(connection) if connection else None,
            )
        ]
        items.extend(
            ProjectIntegrationSummary(
                provider=key,
                display_name=name,
                status="coming_later",
                available=False,
                connection=None,
            )
            for key, name in _DEFERRED_PROVIDERS
        )
        return ProjectIntegrationListResponse(items=items)

    async def get_connection(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> ConnectionResponse:
        connection = await self._require_connection(organization_id, project_id)
        return self._connection_response(connection)

    async def create_connection(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        actor_id: UUID,
        body: ConnectionCreateRequest,
    ) -> ConnectionResponse:
        self._require_enabled()
        await self._load_project(organization_id, project_id)
        installation = await self._load_installation(organization_id, body.installation_id)

        if await self._find_connection(organization_id, project_id) is not None:
            raise ConflictError(
                "This project already has an active GitHub connection.",
                error_code="INTEGRATION_ALREADY_CONNECTED",
            )
        duplicate_repo = await self._session.scalar(
            select(GitHubRepositoryConnection).where(
                GitHubRepositoryConnection.organization_id == organization_id,
                GitHubRepositoryConnection.github_repository_id == body.github_repository_id,
                GitHubRepositoryConnection.disconnected_at.is_(None),
            )
        )
        if duplicate_repo is not None:
            raise ConflictError(
                "This repository is already connected to another project.",
                error_code="REPOSITORY_ALREADY_CONNECTED",
            )

        connection = GitHubRepositoryConnection(
            organization_id=organization_id,
            project_id=project_id,
            github_installation_id=installation.id,
            github_repository_id=body.github_repository_id,
            repository_full_name=body.repository_full_name.strip(),
            repository_url=body.repository_url,
            default_branch=body.default_branch,
            is_active=True,
            is_paused=False,
            auto_create_incidents=body.auto_create_incidents,
            auto_start_analysis=body.auto_start_analysis,
            notify_on_failure=body.notify_on_failure,
            workflow_filters_json=(
                body.workflow_filters.model_dump() if body.workflow_filters else None
            ),
            branch_filters_json=(body.branch_filters.model_dump() if body.branch_filters else None),
            failure_conclusions_json=body.failure_conclusions,
            environment_mapping_json=body.environment_mapping,
            severity_rules_json=body.severity_rules,
            created_by=actor_id,
        )
        self._session.add(connection)
        await self._session.flush()
        connection.installation = installation
        logger.info(
            "github_repository_connected",
            project_id=str(project_id),
            repository_id=body.github_repository_id,
        )
        return self._connection_response(connection)

    async def update_connection(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        body: ConnectionUpdateRequest,
    ) -> ConnectionResponse:
        connection = await self._require_connection(organization_id, project_id)
        if body.auto_create_incidents is not None:
            connection.auto_create_incidents = body.auto_create_incidents
        if body.auto_start_analysis is not None:
            connection.auto_start_analysis = body.auto_start_analysis
        if body.notify_on_failure is not None:
            connection.notify_on_failure = body.notify_on_failure
        if body.workflow_filters is not None:
            connection.workflow_filters_json = body.workflow_filters.model_dump()
        if body.branch_filters is not None:
            connection.branch_filters_json = body.branch_filters.model_dump()
        if body.failure_conclusions is not None:
            connection.failure_conclusions_json = body.failure_conclusions
        if body.environment_mapping is not None:
            connection.environment_mapping_json = body.environment_mapping
        if body.severity_rules is not None:
            connection.severity_rules_json = body.severity_rules
        await self._session.flush()
        return self._connection_response(connection)

    async def set_paused(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        paused: bool,
    ) -> ConnectionResponse:
        connection = await self._require_connection(organization_id, project_id)
        connection.is_paused = paused
        await self._session.flush()
        logger.info(
            "github_connection_pause_changed",
            project_id=str(project_id),
            paused=paused,
        )
        return self._connection_response(connection)

    async def disconnect(self, *, organization_id: UUID, project_id: UUID) -> None:
        connection = await self._require_connection(organization_id, project_id)
        connection.disconnected_at = datetime.now(UTC)
        connection.is_active = False
        await self._session.flush()
        logger.info("github_connection_disconnected", project_id=str(project_id))

    async def test_connection(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> ConnectionTestResponse:
        connection = await self._require_connection(organization_id, project_id)
        installation_reachable = False
        repository_accessible = False
        message = "Connection verified."
        try:
            await self._provider.get_installation(
                connection.installation.github_installation_id,
            )
            installation_reachable = True
            repositories = await self._provider.list_installation_repositories(
                connection.installation.github_installation_id
            )
            repository_accessible = any(
                repo.repository_id == connection.github_repository_id for repo in repositories
            )
            if not repository_accessible:
                message = "The installation no longer grants access to this repository."
        except GitHubProviderError as exc:
            message = exc.message
            connection.last_error = exc.message[:500]

        ok = installation_reachable and repository_accessible
        if ok:
            connection.last_successful_sync_at = datetime.now(UTC)
            connection.last_error = None
        await self._session.flush()
        return ConnectionTestResponse(
            ok=ok,
            checked_at=datetime.now(UTC),
            repository_full_name=connection.repository_full_name,
            installation_reachable=installation_reachable,
            repository_accessible=repository_accessible,
            message=message,
        )

    async def list_workflows(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
    ) -> GitHubWorkflowListResponse:
        connection = await self._require_connection(organization_id, project_id)
        try:
            workflows = await self._provider.list_repository_workflows(
                installation_id=connection.installation.github_installation_id,
                repository_full_name=connection.repository_full_name,
            )
        except GitHubProviderError:
            workflows = []
        return GitHubWorkflowListResponse(
            items=[
                GitHubWorkflowResponse(
                    workflow_id=workflow.workflow_id,
                    name=workflow.name,
                    path=workflow.path,
                    state=workflow.state,
                )
                for workflow in workflows
            ]
        )

    async def list_activity(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        limit: int = 50,
    ) -> WebhookActivityListResponse:
        connection = await self._require_connection(organization_id, project_id)
        deliveries = await WebhookDeliveryService(self._session).list_for_repository(
            repository_id=connection.github_repository_id,
            limit=limit,
        )
        return WebhookActivityListResponse(
            items=[self._activity_item(delivery) for delivery in deliveries]
        )

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    async def _load_project(self, organization_id: UUID, project_id: UUID) -> Project:
        project = await self._session.get(Project, project_id)
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFoundError("Project not found.")
        return project

    async def _load_installation(
        self,
        organization_id: UUID,
        installation_row_id: UUID,
    ) -> GitHubInstallation:
        installation = await self._session.get(GitHubInstallation, installation_row_id)
        if installation is None or installation.organization_id != organization_id:
            raise ResourceNotFoundError("GitHub installation not found.")
        return installation

    async def _find_connection(
        self,
        organization_id: UUID,
        project_id: UUID,
    ) -> GitHubRepositoryConnection | None:
        stmt = (
            select(GitHubRepositoryConnection)
            .where(
                GitHubRepositoryConnection.organization_id == organization_id,
                GitHubRepositoryConnection.project_id == project_id,
                GitHubRepositoryConnection.disconnected_at.is_(None),
            )
            .options(selectinload(GitHubRepositoryConnection.installation))
        )
        return await self._session.scalar(stmt)

    async def _require_connection(
        self,
        organization_id: UUID,
        project_id: UUID,
    ) -> GitHubRepositoryConnection:
        await self._load_project(organization_id, project_id)
        connection = await self._find_connection(organization_id, project_id)
        if connection is None:
            raise ResourceNotFoundError("This project has no GitHub connection.")
        return connection

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    @staticmethod
    def _installation_response(row: GitHubInstallation) -> GitHubInstallationResponse:
        return GitHubInstallationResponse(
            id=row.id,
            github_installation_id=row.github_installation_id,
            github_account_login=row.github_account_login,
            account_type=row.account_type,
            status=row.status,
            repository_selection=row.repository_selection,
            permissions=row.permissions_json,
            installed_at=row.installed_at,
            created_at=row.created_at,
        )

    @staticmethod
    def _connection_response(row: GitHubRepositoryConnection) -> ConnectionResponse:
        workflow_filters = row.workflow_filters_json or {}
        branch_filters = row.branch_filters_json or {}
        return ConnectionResponse(
            id=row.id,
            project_id=row.project_id,
            installation_id=row.github_installation_id,
            github_installation_id=row.installation.github_installation_id,
            github_repository_id=row.github_repository_id,
            repository_full_name=row.repository_full_name,
            repository_url=row.repository_url,
            default_branch=row.default_branch,
            is_active=row.is_active,
            is_paused=row.is_paused,
            auto_create_incidents=row.auto_create_incidents,
            auto_start_analysis=row.auto_start_analysis,
            notify_on_failure=row.notify_on_failure,
            workflow_filters=WorkflowFilters(**workflow_filters)
            if workflow_filters
            else WorkflowFilters(),
            branch_filters=BranchFilters(**branch_filters) if branch_filters else BranchFilters(),
            failure_conclusions=list(
                row.failure_conclusions_json or DEFAULT_FAILURE_CONCLUSIONS,
            ),
            environment_mapping=dict(row.environment_mapping_json or {}),
            severity_rules=dict(row.severity_rules_json or DEFAULT_SEVERITY_RULES),
            last_webhook_at=row.last_webhook_at,
            last_successful_sync_at=row.last_successful_sync_at,
            last_error=row.last_error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _activity_item(delivery: WebhookDelivery) -> WebhookActivityItem:
        snapshot = delivery.sanitised_snapshot or {}
        run = snapshot.get("workflow_run") or {}
        return WebhookActivityItem(
            id=delivery.id,
            delivery_id=delivery.delivery_id,
            event_name=delivery.event_name,
            event_action=delivery.event_action,
            processing_status=delivery.processing_status,
            received_at=delivery.received_at,
            processed_at=delivery.processed_at,
            error_code=delivery.error_code,
            error_message=delivery.error_message_sanitized,
            workflow_name=run.get("name"),
            branch=run.get("head_branch"),
            conclusion=run.get("conclusion"),
            related_incident_id=delivery.related_incident_id,
            related_pipeline_run_id=delivery.related_pipeline_run_id,
        )
