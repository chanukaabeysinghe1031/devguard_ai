"""Integration endpoints — GitHub Actions ingestion (Phase 5B, ADR-005).

The webhook route is authenticated by HMAC signature rather than JWT; every
other route requires organization membership. Connect/disconnect and settings
changes are restricted to organization owners and admins.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.access import require_org_admin, require_org_reader
from app.application.services.github_setup_service import GitHubSetupService
from app.application.services.github_webhook_security import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
    parse_event,
    payload_hash,
    require_valid_signature,
)
from app.application.services.github_webhook_task import run_or_schedule_delivery_processing
from app.application.services.webhook_delivery_service import WebhookDeliveryService
from app.core.config import Settings
from app.domain.enums import WebhookProcessingStatus
from app.domain.exceptions.integration import WebhookConfigurationError
from app.domain.interfaces.github_provider import GitHubProvider
from app.infrastructure.integrations.factory import get_github_provider
from app.schemas.common import MessageResponse
from app.schemas.integration import (
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionUpdateRequest,
    GitHubInstallationListResponse,
    GitHubRepositoryListResponse,
    GitHubStatusResponse,
    GitHubWorkflowListResponse,
    InstallUrlRequest,
    InstallUrlResponse,
    ProjectIntegrationListResponse,
    SetupCompleteRequest,
    SetupCompleteResponse,
    WebhookAcceptedResponse,
    WebhookActivityListResponse,
)

router = APIRouter(tags=["Integrations"])


def _provider(settings: Settings = Depends(get_settings_dep)) -> GitHubProvider:
    return get_github_provider(settings)


def _setup_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
    provider: GitHubProvider = Depends(_provider),
) -> GitHubSetupService:
    return GitHubSetupService(session=session, settings=settings, provider=provider)


# ----------------------------------------------------------------------
# Public webhook receiver (signature authenticated)
# ----------------------------------------------------------------------
@router.post(
    "/integrations/github/webhook",
    response_model=WebhookAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> WebhookAcceptedResponse:
    # The raw body must be read before any JSON parsing so the HMAC is computed
    # over exactly the bytes GitHub signed.
    raw_body = await request.body()
    secret = settings.github_webhook_secret
    if not secret:
        raise WebhookConfigurationError("GITHUB_WEBHOOK_SECRET is not configured.")
    require_valid_signature(raw_body, request.headers.get(SIGNATURE_HEADER), secret=secret)

    event = parse_event(
        raw_body=raw_body,
        event_name=request.headers.get(EVENT_HEADER),
        delivery_id=request.headers.get(DELIVERY_HEADER),
    )
    if event.event_name == "ping":
        return WebhookAcceptedResponse(
            ok=True,
            delivery_id=event.delivery_id,
            processing_status=WebhookProcessingStatus.IGNORED.value,
        )

    deliveries = WebhookDeliveryService(session)
    delivery, created = await deliveries.create_if_new(
        delivery_id=event.delivery_id,
        event_name=event.event_name,
        event_action=event.event_action,
        installation_id=event.installation_id,
        repository_id=event.repository_id,
        payload_hash=payload_hash(raw_body),
        sanitised_snapshot=event.snapshot,
        signature_valid=True,
    )
    if not created:
        return WebhookAcceptedResponse(
            ok=True,
            delivery_id=delivery.delivery_id,
            duplicate=True,
            processing_status=delivery.processing_status,
        )

    await deliveries.mark_status(delivery, WebhookProcessingStatus.VALIDATED)
    if not event.is_supported:
        await deliveries.mark_ignored(delivery, "event_not_supported")
        return WebhookAcceptedResponse(
            ok=True,
            delivery_id=delivery.delivery_id,
            processing_status=delivery.processing_status,
        )

    delivery_row_id = delivery.id
    await deliveries.mark_status(delivery, WebhookProcessingStatus.QUEUED)
    await run_or_schedule_delivery_processing(
        delivery_row_id,
        settings=settings,
        session=session,
        background_tasks=background_tasks,
    )
    refreshed = await session.get(type(delivery), delivery_row_id)
    return WebhookAcceptedResponse(
        ok=True,
        delivery_id=event.delivery_id,
        processing_status=refreshed.processing_status if refreshed else None,
    )


# ----------------------------------------------------------------------
# Organization-level GitHub App configuration
# ----------------------------------------------------------------------
@router.get("/integrations/github/status", response_model=GitHubStatusResponse)
async def get_github_status(
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> GitHubStatusResponse:
    _, organization_id, _ = ctx
    return await service.status(organization_id=organization_id)


@router.post("/integrations/github/install-url", response_model=InstallUrlResponse)
async def create_github_install_url(
    body: InstallUrlRequest,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> InstallUrlResponse:
    user, organization_id, _ = ctx
    return await service.build_install_url(
        organization_id=organization_id,
        user_id=user.id,
        project_id=body.project_id,
    )


@router.get("/integrations/github/setup", response_model=SetupCompleteResponse)
async def complete_github_setup_via_redirect(
    installation_id: int = Query(gt=0),
    state: str = Query(min_length=1),
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> SetupCompleteResponse:
    _, organization_id, _ = ctx
    return await service.complete_setup(
        organization_id=organization_id,
        installation_id=installation_id,
        state=state,
    )


@router.post("/integrations/github/setup", response_model=SetupCompleteResponse)
async def complete_github_setup(
    body: SetupCompleteRequest,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> SetupCompleteResponse:
    _, organization_id, _ = ctx
    return await service.complete_setup(
        organization_id=organization_id,
        installation_id=body.installation_id,
        state=body.state,
    )


@router.get("/integrations/github/installations", response_model=GitHubInstallationListResponse)
async def list_github_installations(
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> GitHubInstallationListResponse:
    _, organization_id, _ = ctx
    return await service.list_installations(organization_id=organization_id)


@router.get(
    "/integrations/github/installations/{installation_id}/repositories",
    response_model=GitHubRepositoryListResponse,
)
async def list_github_installation_repositories(
    installation_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> GitHubRepositoryListResponse:
    _, organization_id, _ = ctx
    return await service.list_repositories(
        organization_id=organization_id,
        installation_row_id=installation_id,
    )


@router.post(
    "/integrations/github/installations/{installation_id}/sync",
    response_model=GitHubRepositoryListResponse,
)
async def sync_github_installation_repositories(
    installation_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> GitHubRepositoryListResponse:
    """Refresh this organization's view of the installation's repositories."""
    _, organization_id, _ = ctx
    return await service.sync_repositories(
        organization_id=organization_id,
        installation_row_id=installation_id,
    )


@router.delete(
    "/integrations/github/installations/{installation_id}/link",
    response_model=MessageResponse,
)
async def unlink_github_installation(
    installation_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> MessageResponse:
    """Revoke this organization's access grant only.

    The shared GitHub App installation itself, and any other organization's
    access to it, are unaffected.
    """
    _, organization_id, _ = ctx
    await service.disconnect_organization_access(
        organization_id=organization_id,
        installation_row_id=installation_id,
    )
    return MessageResponse(message="GitHub installation access removed from this organization.")


# ----------------------------------------------------------------------
# Project-scoped integration management
# ----------------------------------------------------------------------
@router.get(
    "/projects/{project_id}/integrations",
    response_model=ProjectIntegrationListResponse,
)
async def list_project_integrations(
    project_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> ProjectIntegrationListResponse:
    _, organization_id, _ = ctx
    return await service.list_project_integrations(
        organization_id=organization_id,
        project_id=project_id,
    )


@router.get("/projects/{project_id}/integrations/github", response_model=ConnectionResponse)
async def get_project_github_connection(
    project_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionResponse:
    _, organization_id, _ = ctx
    return await service.get_connection(organization_id=organization_id, project_id=project_id)


@router.post(
    "/projects/{project_id}/integrations/github",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_project_github(
    project_id: UUID,
    body: ConnectionCreateRequest,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionResponse:
    user, organization_id, _ = ctx
    return await service.create_connection(
        organization_id=organization_id,
        project_id=project_id,
        actor_id=user.id,
        body=body,
    )


@router.patch("/projects/{project_id}/integrations/github", response_model=ConnectionResponse)
async def update_project_github(
    project_id: UUID,
    body: ConnectionUpdateRequest,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionResponse:
    _, organization_id, _ = ctx
    return await service.update_connection(
        organization_id=organization_id,
        project_id=project_id,
        body=body,
    )


@router.post(
    "/projects/{project_id}/integrations/github/test",
    response_model=ConnectionTestResponse,
)
async def test_project_github(
    project_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionTestResponse:
    _, organization_id, _ = ctx
    return await service.test_connection(organization_id=organization_id, project_id=project_id)


@router.post(
    "/projects/{project_id}/integrations/github/pause",
    response_model=ConnectionResponse,
)
async def pause_project_github(
    project_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionResponse:
    _, organization_id, _ = ctx
    return await service.set_paused(
        organization_id=organization_id,
        project_id=project_id,
        paused=True,
    )


@router.post(
    "/projects/{project_id}/integrations/github/resume",
    response_model=ConnectionResponse,
)
async def resume_project_github(
    project_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> ConnectionResponse:
    _, organization_id, _ = ctx
    return await service.set_paused(
        organization_id=organization_id,
        project_id=project_id,
        paused=False,
    )


@router.delete("/projects/{project_id}/integrations/github", response_model=MessageResponse)
async def disconnect_project_github(
    project_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: GitHubSetupService = Depends(_setup_service),
) -> MessageResponse:
    _, organization_id, _ = ctx
    await service.disconnect(organization_id=organization_id, project_id=project_id)
    return MessageResponse(message="GitHub connection removed.")


@router.get(
    "/projects/{project_id}/integrations/github/workflows",
    response_model=GitHubWorkflowListResponse,
)
async def list_project_github_workflows(
    project_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> GitHubWorkflowListResponse:
    _, organization_id, _ = ctx
    return await service.list_workflows(organization_id=organization_id, project_id=project_id)


@router.get(
    "/projects/{project_id}/integrations/github/activity",
    response_model=WebhookActivityListResponse,
)
async def list_project_github_activity(
    project_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: tuple = Depends(require_org_reader),
    service: GitHubSetupService = Depends(_setup_service),
) -> WebhookActivityListResponse:
    _, organization_id, _ = ctx
    return await service.list_activity(
        organization_id=organization_id,
        project_id=project_id,
        limit=limit,
    )
