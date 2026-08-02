"""Automated GitHub Actions failure ingestion (ADR-005).

Turns a signature-validated ``workflow_run.completed`` delivery into a pipeline
run, an incident, persisted logs, and an analysis run — reusing the existing
upload, analysis, and notification services. Observe/diagnose only: nothing in
this module ever writes to GitHub.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.analysis_task import run_or_schedule_analysis
from app.application.services.github_log_extractor import extract_log_files
from app.application.services.notification_service import NotificationService
from app.application.services.upload_service import UploadService
from app.application.services.webhook_delivery_service import WebhookDeliveryService
from app.core.config import Settings
from app.domain.enums import (
    CiProvider,
    GitHubInstallationAccessStatus,
    GitHubInstallationStatus,
    IncidentSeverity,
    IncidentStatus,
    PipelineRunStatus,
    WebhookConnectionProcessingStatus,
)
from app.domain.exceptions.integration import GitHubProviderError, LogArchiveError
from app.domain.interfaces.github_provider import GitHubProvider
from app.domain.interfaces.storage_provider import FileStorage
from app.domain.services.github_event_filters import (
    evaluate_workflow_run,
    resolve_environment,
    resolve_severity,
)
from app.infrastructure.database.models.github_installation import GitHubInstallation
from app.infrastructure.database.models.github_installation_organization_access import (
    GitHubInstallationOrganizationAccess,
)
from app.infrastructure.database.models.github_repository_connection import (
    GitHubRepositoryConnection,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.webhook_delivery import WebhookDelivery
from app.schemas.analysis import AnalysisOptions, StartAnalysisRequest

logger = structlog.get_logger(__name__)

INCIDENT_SOURCE_GITHUB = "github_webhook"
SYSTEM_ACTOR = "system"

_UNSAFE_TITLE_CHARS = re.compile(r"[\r\n\t]+")


def _safe_text(value: str | None, *, limit: int) -> str | None:
    if not value:
        return None
    cleaned = _UNSAFE_TITLE_CHARS.sub(" ", value)
    cleaned = "".join(char for char in cleaned if char.isprintable()).strip()
    return cleaned[:limit] or None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass
class _ConnectionOutcome:
    """Result of processing one delivery for one repository connection."""

    pipeline_run: PipelineRun | None = None
    incident: Incident | None = None
    skip_reason: str | None = None


class GitHubIngestionService:
    """Processes a persisted webhook delivery into DevGuard domain objects."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        provider: GitHubProvider,
        storage: FileStorage,
    ) -> None:
        self._session = session
        self._settings = settings
        self._provider = provider
        self._storage = storage
        self._deliveries = WebhookDeliveryService(session)
        self._notifications = NotificationService(session)

    async def process_delivery_id(
        self,
        delivery_row_id: UUID,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        delivery = await self._session.get(WebhookDelivery, delivery_row_id)
        if delivery is None:
            logger.warning("webhook_delivery_missing", delivery_row_id=str(delivery_row_id))
            return
        await self.process(delivery, background_tasks=background_tasks)

    async def process(
        self,
        delivery: WebhookDelivery,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> None:
        """Drive the delivery state machine; never raises to the caller."""
        try:
            if delivery.event_name == "workflow_run" and delivery.event_action == "completed":
                await self._process_workflow_run(delivery, background_tasks=background_tasks)
            elif delivery.event_name == "installation":
                await self._process_installation_event(delivery)
            else:
                await self._deliveries.mark_ignored(delivery, "event_not_ingestible")
        except (GitHubProviderError, LogArchiveError) as exc:
            await self._deliveries.mark_failed(
                delivery,
                error_code=exc.error_code,
                error_message=exc.message,
                retriable=getattr(exc, "retriable", False),
                max_attempts=self._settings.github_max_delivery_attempts,
            )
        except Exception as exc:  # noqa: BLE001 - delivery state must always settle
            logger.exception("webhook_delivery_processing_error", delivery_id=delivery.delivery_id)
            await self._deliveries.mark_failed(
                delivery,
                error_code="INGESTION_ERROR",
                error_message=type(exc).__name__,
                retriable=False,
                max_attempts=self._settings.github_max_delivery_attempts,
            )

    # ------------------------------------------------------------------
    # workflow_run.completed
    # ------------------------------------------------------------------
    async def _process_workflow_run(
        self,
        delivery: WebhookDelivery,
        *,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """Fan a single delivery out to every matching tenant connection.

        A GitHub App installation may be shared by many DevGuard
        organizations, so one delivery can legitimately match several
        repository connections across different tenants. Each connection is
        processed and settled independently — one tenant's failure must
        never mask or abort another's outcome.
        """
        snapshot = delivery.sanitised_snapshot or {}
        run = snapshot.get("workflow_run") or {}
        run_id = run.get("id")
        if delivery.repository_id is None or run_id is None:
            await self._deliveries.mark_ignored(delivery, "missing_repository_or_run")
            return

        connections = await self._find_active_connections(
            repository_id=delivery.repository_id,
            github_installation_numeric_id=delivery.installation_id,
        )
        if not connections:
            await self._deliveries.mark_ignored(delivery, "no_active_connection")
            return

        logger.info(
            "github_webhook_fan_out",
            delivery_id=delivery.delivery_id,
            repository_id=delivery.repository_id,
            fan_out_count=len(connections),
        )
        await self._deliveries.mark_processing_started(delivery)

        outcome_statuses: list[WebhookConnectionProcessingStatus] = []
        last_pipeline_run_id: UUID | None = None
        last_incident_id: UUID | None = None

        for connection in connections:
            processing = await self._deliveries.ensure_connection_processing(
                delivery=delivery, connection=connection
            )
            if processing.status in (
                WebhookConnectionProcessingStatus.COMPLETE.value,
                WebhookConnectionProcessingStatus.SKIPPED.value,
            ):
                # Already settled for this connection (e.g. a replayed or
                # concurrently retried delivery) — do not reprocess.
                outcome_statuses.append(WebhookConnectionProcessingStatus(processing.status))
                last_pipeline_run_id = processing.pipeline_run_id or last_pipeline_run_id
                last_incident_id = processing.incident_id or last_incident_id
                continue

            try:
                await self._deliveries.mark_connection_processing_started(processing)
                outcome = await self._process_workflow_run_for_connection(
                    connection=connection,
                    run=run,
                    background_tasks=background_tasks,
                )
            except (GitHubProviderError, LogArchiveError) as exc:
                await self._deliveries.mark_connection_processing_failed(
                    processing,
                    error_code=exc.error_code,
                    error_message=exc.message,
                    retriable=getattr(exc, "retriable", False),
                )
                outcome_statuses.append(
                    WebhookConnectionProcessingStatus.RETRYABLE
                    if getattr(exc, "retriable", False)
                    else WebhookConnectionProcessingStatus.FAILED
                )
                continue
            except Exception as exc:  # noqa: BLE001 - one tenant must never abort others
                logger.exception(
                    "github_connection_processing_error",
                    delivery_id=delivery.delivery_id,
                    connection_id=str(connection.id),
                )
                await self._deliveries.mark_connection_processing_failed(
                    processing,
                    error_code="INGESTION_ERROR",
                    error_message=type(exc).__name__,
                    retriable=False,
                )
                outcome_statuses.append(WebhookConnectionProcessingStatus.FAILED)
                continue

            if outcome.skip_reason is not None:
                await self._deliveries.mark_connection_processing_skipped(
                    processing, outcome.skip_reason
                )
                outcome_statuses.append(WebhookConnectionProcessingStatus.SKIPPED)
                continue

            await self._deliveries.mark_connection_processing_completed(
                processing,
                pipeline_run_id=outcome.pipeline_run.id if outcome.pipeline_run else None,
                incident_id=outcome.incident.id if outcome.incident else None,
            )
            outcome_statuses.append(WebhookConnectionProcessingStatus.COMPLETE)
            if outcome.pipeline_run is not None:
                last_pipeline_run_id = outcome.pipeline_run.id
            if outcome.incident is not None:
                last_incident_id = outcome.incident.id

        await self._settle_fan_out_delivery(
            delivery,
            outcome_statuses=outcome_statuses,
            pipeline_run_id=last_pipeline_run_id,
            incident_id=last_incident_id,
        )

    async def _settle_fan_out_delivery(
        self,
        delivery: WebhookDelivery,
        *,
        outcome_statuses: list[WebhookConnectionProcessingStatus],
        pipeline_run_id: UUID | None,
        incident_id: UUID | None,
    ) -> None:
        """Aggregate independent per-connection outcomes into one delivery status.

        The delivery's own ``related_*`` fields are best-effort pointers to
        the last successful connection outcome; the authoritative per-tenant
        record is ``webhook_delivery_connection_processing``.
        """
        has_retryable = any(
            status == WebhookConnectionProcessingStatus.RETRYABLE for status in outcome_statuses
        )
        has_failed = any(
            status == WebhookConnectionProcessingStatus.FAILED for status in outcome_statuses
        )
        has_complete = any(
            status == WebhookConnectionProcessingStatus.COMPLETE for status in outcome_statuses
        )
        if has_retryable:
            await self._deliveries.mark_failed(
                delivery,
                error_code="CONNECTION_PROCESSING_RETRYABLE",
                error_message="One or more organization connections require a retry.",
                retriable=True,
                max_attempts=self._settings.github_max_delivery_attempts,
            )
        elif has_failed:
            await self._deliveries.mark_failed(
                delivery,
                error_code="CONNECTION_PROCESSING_FAILED",
                error_message=(
                    "One or more organization connections failed to process this delivery."
                ),
                retriable=False,
                max_attempts=self._settings.github_max_delivery_attempts,
            )
        elif has_complete:
            await self._deliveries.mark_completed(
                delivery,
                pipeline_run_id=pipeline_run_id,
                incident_id=incident_id,
            )
        else:
            await self._deliveries.mark_ignored(delivery, "all_connections_skipped")

    async def _process_workflow_run_for_connection(
        self,
        *,
        connection: GitHubRepositoryConnection,
        run: dict[str, Any],
        background_tasks: BackgroundTasks | None,
    ) -> _ConnectionOutcome:
        """Apply this connection's filters/automation to one workflow run."""
        decision = evaluate_workflow_run(
            conclusion=run.get("conclusion"),
            workflow_name=run.get("name"),
            branch=run.get("head_branch"),
            default_branch=connection.default_branch,
            failure_conclusions=connection.failure_conclusions_json,
            workflow_filters=connection.workflow_filters_json,
            branch_filters=connection.branch_filters_json,
        )
        connection.last_webhook_at = datetime.now(UTC)
        if not decision.should_ingest:
            await self._session.flush()
            return _ConnectionOutcome(skip_reason=decision.reason)

        run = await self._enrich_run_metadata(connection, run)
        pipeline_run = await self._upsert_pipeline_run(connection, run)

        if not connection.auto_create_incidents:
            connection.last_successful_sync_at = datetime.now(UTC)
            return _ConnectionOutcome(pipeline_run=pipeline_run)

        incident, created = await self._get_or_create_incident(connection, pipeline_run, run)

        if not created:
            connection.last_successful_sync_at = datetime.now(UTC)
            return _ConnectionOutcome(pipeline_run=pipeline_run, incident=incident)

        if connection.notify_on_failure:
            await self._notify_incident_created(connection, incident, run)

        if connection.auto_start_analysis:
            await self._ingest_logs_and_analyse_for_connection(
                connection=connection,
                incident=incident,
                run=run,
                background_tasks=background_tasks,
            )

        connection.last_successful_sync_at = datetime.now(UTC)
        connection.last_error = None
        logger.info(
            "github_incident_ingested",
            incident_id=str(incident.id),
            organization_id=str(connection.organization_id),
            project_id=str(connection.project_id),
            repository_id=connection.github_repository_id,
        )
        return _ConnectionOutcome(pipeline_run=pipeline_run, incident=incident)

    async def _process_installation_event(self, delivery: WebhookDelivery) -> None:
        action = delivery.event_action or ""
        status_by_action = {
            "suspend": GitHubInstallationStatus.SUSPENDED,
            "unsuspend": GitHubInstallationStatus.ACTIVE,
            "deleted": GitHubInstallationStatus.DELETED,
        }
        new_status = status_by_action.get(action)
        if new_status is None or delivery.installation_id is None:
            await self._deliveries.mark_ignored(delivery, "installation_action_not_handled")
            return

        installation = await self._session.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.github_installation_id == delivery.installation_id
            )
        )
        if installation is None:
            await self._deliveries.mark_ignored(delivery, "installation_not_registered")
            return

        installation.status = new_status.value
        installation.suspended_at = (
            datetime.now(UTC) if new_status == GitHubInstallationStatus.SUSPENDED else None
        )
        await self._session.flush()

        # Propagate to every organization's independent access grant — a
        # shared installation being suspended/deleted/restored on GitHub
        # affects all tenants using it, except those who already manually
        # disconnected (which must not be silently reactivated).
        access_status_by_action = {
            "suspend": GitHubInstallationAccessStatus.SUSPENDED,
            "deleted": GitHubInstallationAccessStatus.INSTALLATION_UNAVAILABLE,
        }
        new_access_status = access_status_by_action.get(action)
        accesses = list(
            (
                await self._session.scalars(
                    select(GitHubInstallationOrganizationAccess).where(
                        GitHubInstallationOrganizationAccess.installation_id == installation.id
                    )
                )
            ).all()
        )
        updated = 0
        for access in accesses:
            if access.status == GitHubInstallationAccessStatus.DISCONNECTED.value:
                continue
            if action == "unsuspend":
                access.status = GitHubInstallationAccessStatus.ACTIVE.value
                updated += 1
            elif new_access_status is not None:
                access.status = new_access_status.value
                updated += 1
        await self._session.flush()

        logger.info(
            "github_installation_status_changed",
            github_installation_id=delivery.installation_id,
            action=action,
            access_grants_updated=updated,
        )
        await self._deliveries.mark_completed(delivery)

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    async def _find_active_connections(
        self,
        *,
        repository_id: int,
        github_installation_numeric_id: int | None,
    ) -> list[GitHubRepositoryConnection]:
        """Every live, active-access connection to this repository.

        Joined through the connection's own ``installation_access_id`` so
        that each tenant's fan-out eligibility is judged by that tenant's
        independent access grant, not by the (legacy, single-value)
        installation-level organization link.
        """
        stmt = (
            select(GitHubRepositoryConnection)
            .join(
                GitHubInstallation,
                GitHubInstallation.id == GitHubRepositoryConnection.github_installation_id,
            )
            .join(
                GitHubInstallationOrganizationAccess,
                GitHubInstallationOrganizationAccess.id
                == GitHubRepositoryConnection.installation_access_id,
            )
            .where(
                GitHubRepositoryConnection.github_repository_id == repository_id,
                GitHubRepositoryConnection.disconnected_at.is_(None),
                GitHubRepositoryConnection.is_active.is_(True),
                GitHubRepositoryConnection.is_paused.is_(False),
                GitHubInstallationOrganizationAccess.status
                == GitHubInstallationAccessStatus.ACTIVE.value,
                GitHubInstallation.status == GitHubInstallationStatus.ACTIVE.value,
            )
            .options(
                selectinload(GitHubRepositoryConnection.installation),
                selectinload(GitHubRepositoryConnection.project),
            )
        )
        if github_installation_numeric_id is not None:
            stmt = stmt.where(
                GitHubInstallation.github_installation_id == github_installation_numeric_id
            )
        return list((await self._session.scalars(stmt)).all())

    async def _enrich_run_metadata(
        self,
        connection: GitHubRepositoryConnection,
        run: dict[str, Any],
    ) -> dict[str, Any]:
        """Confirm the run against the API; soft-fail back to the webhook snapshot."""
        try:
            detail = await self._provider.get_workflow_run(
                installation_id=connection.installation.github_installation_id,
                repository_full_name=connection.repository_full_name,
                run_id=int(run["id"]),
            )
        except GitHubProviderError as exc:
            logger.info("github_run_metadata_unavailable", error_code=exc.error_code)
            return run

        enriched = dict(run)
        enriched.setdefault("name", detail.name)
        enriched["conclusion"] = detail.conclusion or run.get("conclusion")
        enriched["head_branch"] = detail.head_branch or run.get("head_branch")
        enriched["head_sha"] = detail.head_sha or run.get("head_sha")
        enriched["run_attempt"] = detail.run_attempt or run.get("run_attempt")
        enriched["actor_login"] = detail.actor_login or run.get("actor_login")
        enriched["html_url"] = detail.html_url or run.get("html_url")
        return enriched

    async def _upsert_pipeline_run(
        self,
        connection: GitHubRepositoryConnection,
        run: dict[str, Any],
    ) -> PipelineRun:
        external_run_id = str(run["id"])
        existing = await self._session.scalar(
            select(PipelineRun).where(
                PipelineRun.project_id == connection.project_id,
                PipelineRun.provider == CiProvider.GITHUB_ACTIONS,
                PipelineRun.external_run_id == external_run_id,
            )
        )
        started_at = _parse_timestamp(run.get("run_started_at"))
        completed_at = _parse_timestamp(run.get("updated_at"))
        environment = resolve_environment(
            run.get("head_branch"),
            connection.environment_mapping_json,
        )
        metadata = {
            "run_attempt": run.get("run_attempt"),
            "run_number": run.get("run_number"),
            "conclusion": run.get("conclusion"),
            "event": run.get("event"),
            "repository_full_name": connection.repository_full_name,
            "github_repository_id": connection.github_repository_id,
        }

        if existing is not None:
            existing.status = PipelineRunStatus.FAILED
            existing.completed_at = completed_at or existing.completed_at
            existing.raw_metadata = {**(existing.raw_metadata or {}), **metadata}
            await self._session.flush()
            return existing

        pipeline_run = PipelineRun(
            project_id=connection.project_id,
            external_run_id=external_run_id,
            provider=CiProvider.GITHUB_ACTIONS,
            workflow_name=_safe_text(run.get("name"), limit=255),
            branch=_safe_text(run.get("head_branch"), limit=255),
            commit_sha=_safe_text(run.get("head_sha"), limit=100),
            triggered_by=_safe_text(run.get("actor_login"), limit=255),
            environment=_safe_text(environment, limit=50),
            status=PipelineRunStatus.FAILED,
            started_at=started_at,
            completed_at=completed_at,
            source_url=_safe_text(run.get("html_url"), limit=2000),
            raw_metadata=metadata,
        )
        self._session.add(pipeline_run)
        await self._session.flush()
        return pipeline_run

    async def _get_or_create_incident(
        self,
        connection: GitHubRepositoryConnection,
        pipeline_run: PipelineRun,
        run: dict[str, Any],
    ) -> tuple[Incident, bool]:
        existing = await self._session.scalar(
            select(Incident).where(
                Incident.pipeline_run_id == pipeline_run.id,
                Incident.source == INCIDENT_SOURCE_GITHUB,
            )
        )
        if existing is not None:
            return existing, False

        environment = resolve_environment(
            run.get("head_branch"),
            connection.environment_mapping_json,
        )
        severity_value = resolve_severity(environment, connection.severity_rules_json)
        try:
            severity = IncidentSeverity(severity_value)
        except ValueError:
            severity = IncidentSeverity.MEDIUM

        workflow_name = _safe_text(run.get("name"), limit=80) or "Workflow"
        branch = _safe_text(run.get("head_branch"), limit=80) or "unknown branch"
        conclusion = _safe_text(run.get("conclusion"), limit=40) or "failure"
        title = _safe_text(
            f"{workflow_name} {conclusion} on {branch} ({connection.repository_full_name})",
            limit=255,
        )
        description = _safe_text(
            f"GitHub Actions run #{run.get('run_number')} for "
            f"{connection.repository_full_name} finished with conclusion "
            f"'{conclusion}' on branch '{branch}'.",
            limit=2000,
        )

        now = datetime.now(UTC)
        incident = Incident(
            organization_id=connection.organization_id,
            project_id=connection.project_id,
            pipeline_run_id=pipeline_run.id,
            title=title or "GitHub Actions workflow failure",
            description=description,
            source=INCIDENT_SOURCE_GITHUB,
            status=IncidentStatus.DETECTED,
            severity=severity,
            environment=_safe_text(environment, limit=50),
            detected_at=now,
            created_by=None,
            tags={
                "github": {
                    "repository_full_name": connection.repository_full_name,
                    "repository_id": connection.github_repository_id,
                    "run_id": run.get("id"),
                    "run_attempt": run.get("run_attempt"),
                    "workflow_name": _safe_text(run.get("name"), limit=255),
                    "conclusion": conclusion,
                    "html_url": _safe_text(run.get("html_url"), limit=2000),
                }
            },
        )
        self._session.add(incident)
        await self._session.flush()

        self._add_timeline_event(
            organization_id=connection.organization_id,
            incident_id=incident.id,
            event_type="incident_created",
            title="Incident detected from GitHub Actions",
            description=description,
            metadata={
                "connection_id": str(connection.id),
                "pipeline_run_id": str(pipeline_run.id),
                "run_id": run.get("id"),
            },
        )
        await self._session.flush()
        return incident, True

    async def _ingest_logs_and_analyse_for_connection(
        self,
        *,
        connection: GitHubRepositoryConnection,
        incident: Incident,
        run: dict[str, Any],
        background_tasks: BackgroundTasks | None,
    ) -> None:
        try:
            archive = await self._provider.download_workflow_run_logs(
                installation_id=connection.installation.github_installation_id,
                repository_full_name=connection.repository_full_name,
                run_id=int(run["id"]),
            )
        except GitHubProviderError as exc:
            connection.last_error = exc.message[:500]
            self._add_timeline_event(
                organization_id=incident.organization_id,
                incident_id=incident.id,
                event_type="log_ingestion_failed",
                title="Workflow logs could not be downloaded",
                description=exc.message[:500],
            )
            await self._session.flush()
            return

        if not archive:
            self._add_timeline_event(
                organization_id=incident.organization_id,
                incident_id=incident.id,
                event_type="log_ingestion_skipped",
                title="No workflow logs available",
                description="GitHub returned no log archive for this run.",
            )
            await self._session.flush()
            return

        try:
            entries = extract_log_files(archive, settings=self._settings)
        except LogArchiveError as exc:
            connection.last_error = exc.message[:500]
            self._add_timeline_event(
                organization_id=incident.organization_id,
                incident_id=incident.id,
                event_type="log_ingestion_failed",
                title="Workflow log archive rejected",
                description=exc.message[:500],
            )
            await self._session.flush()
            return

        entries = entries[: self._settings.max_files_per_upload]
        uploads = UploadService(
            session=self._session,
            settings=self._settings,
            storage=self._storage,
        )
        organization_id = connection.organization_id
        try:
            stored = await uploads.ingest_system_files(
                organization_id=organization_id,
                incident_id=incident.id,
                files=[(name, content) for name, content in entries],
                file_category="ci_log",
                description=f"GitHub Actions run {run.get('id')} logs",
            )
        except Exception as exc:  # noqa: BLE001 - log persistence must not abort ingestion
            logger.warning("github_log_persist_failed", error=type(exc).__name__)
            self._add_timeline_event(
                organization_id=incident.organization_id,
                incident_id=incident.id,
                event_type="log_ingestion_failed",
                title="Workflow logs could not be stored",
                description=type(exc).__name__,
            )
            await self._session.flush()
            return

        from app.application.services.analysis_run_service import AnalysisRunService

        analysis_file_ids = [item.id for item in stored.files]

        if self._settings.github_artifact_acquisition_enabled:
            analysis_file_ids = await self._acquire_extended_artifacts(
                connection=connection,
                incident=incident,
                run=run,
                uploads=uploads,
                existing_file_ids=analysis_file_ids,
                failed_log_present=bool(stored.files),
            )

        analysis_service = AnalysisRunService(self._session)
        accepted = await analysis_service.start_analysis(
            organization_id=organization_id,
            incident_id=incident.id,
            requested_by=connection.created_by,
            body=StartAnalysisRequest(
                analysis_type="full",
                file_ids=analysis_file_ids,
                options=AnalysisOptions(),
            ),
            system_initiated=True,
        )
        await run_or_schedule_analysis(
            accepted.analysis_run_id,
            settings=self._settings,
            session=self._session,
            background_tasks=background_tasks,
        )

    async def _acquire_extended_artifacts(
        self,
        *,
        connection: GitHubRepositoryConnection,
        incident: Incident,
        run: dict[str, Any],
        uploads: UploadService,
        existing_file_ids: list[UUID],
        failed_log_present: bool,
    ) -> list[UUID]:
        """Soft-fail GitHub artifact acquisition; never abort log-based analysis."""
        from app.ai.artifacts.github_acquisition import GitHubArtifactAcquisition

        file_ids = list(existing_file_ids)
        try:
            acquisition = GitHubArtifactAcquisition(self._provider, self._settings)
            collected = await acquisition.collect(
                installation_id=connection.installation.github_installation_id,
                repository_full_name=connection.repository_full_name,
                run=run,
                failed_log_present=failed_log_present,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("github_artifact_acquisition_failed", error=type(exc).__name__)
            self._add_timeline_event(
                organization_id=incident.organization_id,
                incident_id=incident.id,
                event_type="artifact_acquisition_failed",
                title="Extended GitHub artifact acquisition failed",
                description=type(exc).__name__,
            )
            await self._session.flush()
            return file_ids

        extra_files: list[tuple[str | None, bytes]] = []
        for artifact in collected.artifacts:
            if not artifact.content:
                continue
            extra_files.append((artifact.filename, artifact.content.encode("utf-8")))

        if extra_files:
            try:
                stored_extra = await uploads.ingest_system_files(
                    organization_id=connection.organization_id,
                    incident_id=incident.id,
                    files=extra_files,
                    file_category="github_artifact",
                    description=f"GitHub extended artifacts for run {run.get('id')}",
                )
                file_ids.extend(item.id for item in stored_extra.files)
            except Exception as exc:  # noqa: BLE001
                logger.warning("github_artifact_persist_failed", error=type(exc).__name__)
                self._add_timeline_event(
                    organization_id=incident.organization_id,
                    incident_id=incident.id,
                    event_type="artifact_acquisition_partial",
                    title="Some GitHub artifacts could not be stored",
                    description=type(exc).__name__,
                    metadata={
                        "available": collected.available,
                        "missing": collected.missing,
                        "error_codes": [e.code for e in collected.errors],
                    },
                )
                await self._session.flush()
                return file_ids

        self._add_timeline_event(
            organization_id=incident.organization_id,
            incident_id=incident.id,
            event_type="artifact_acquisition_completed",
            title="Extended GitHub artifacts collected",
            description=(
                f"{len(collected.artifacts)} artifact(s); "
                f"missing={len(collected.missing)}; errors={len(collected.errors)}"
            ),
            metadata={
                "available": collected.available,
                "missing": collected.missing,
                "error_codes": [e.code for e in collected.errors],
            },
        )
        await self._session.flush()
        return file_ids

    async def _notify_incident_created(
        self,
        connection: GitHubRepositoryConnection,
        incident: Incident,
        run: dict[str, Any],
    ) -> None:
        recipients = set(
            await self._notifications.list_organization_recipient_ids(
                organization_id=connection.organization_id
            )
        )
        if connection.created_by:
            recipients.add(connection.created_by)
        if incident.current_assignee_id:
            recipients.add(incident.current_assignee_id)

        message = (
            f"GitHub Actions detected a failure in {connection.repository_full_name} "
            f"({_safe_text(run.get('head_branch'), limit=80) or 'unknown branch'})."
        )
        for user_id in recipients:
            await self._notifications.notify_incident_created(
                user_id=user_id,
                incident_id=incident.id,
                title=incident.title,
                message=message,
                severity=incident.severity.value,
            )

    def _add_timeline_event(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        event_type: str,
        title: str,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            IncidentEvent(
                organization_id=organization_id,
                incident_id=incident_id,
                event_type=event_type,
                actor_type=SYSTEM_ACTOR,
                actor_user_id=None,
                title=title[:255],
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )
