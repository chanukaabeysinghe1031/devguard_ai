"""Organization invitation endpoints (Phase 5C — link delivery, no SMTP)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.access import require_org_admin
from app.application.services.invitation_service import InvitationService
from app.core.config import Settings
from app.schemas.auth import TokenResponse
from app.schemas.organization import (
    AcceptInvitationRequest,
    CreateInvitationRequest,
    InvitationCreatedResponse,
    InvitationPreviewResponse,
    InvitationResponse,
)

router = APIRouter(tags=["Invitations"])


def _service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> InvitationService:
    return InvitationService(session=session, settings=settings)


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    organization_id: UUID,
    body: CreateInvitationRequest,
    ctx: tuple = Depends(require_org_admin),
    service: InvitationService = Depends(_service),
) -> InvitationCreatedResponse:
    user, org_id, _ = ctx
    _assert_same_org(organization_id, org_id)
    return await service.create(
        organization_id=organization_id,
        invited_by=user.id,
        body=body,
    )


@router.get(
    "/organizations/{organization_id}/invitations",
    response_model=list[InvitationResponse],
)
async def list_invitations(
    organization_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: InvitationService = Depends(_service),
) -> list[InvitationResponse]:
    _, org_id, _ = ctx
    _assert_same_org(organization_id, org_id)
    return await service.list_invitations(organization_id)


@router.post(
    "/organizations/{organization_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationResponse,
)
async def revoke_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: InvitationService = Depends(_service),
) -> InvitationResponse:
    _, org_id, _ = ctx
    _assert_same_org(organization_id, org_id)
    return await service.revoke(organization_id=organization_id, invitation_id=invitation_id)


@router.post(
    "/organizations/{organization_id}/invitations/{invitation_id}/resend",
    response_model=InvitationCreatedResponse,
)
async def resend_invitation(
    organization_id: UUID,
    invitation_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: InvitationService = Depends(_service),
) -> InvitationCreatedResponse:
    user, org_id, _ = ctx
    _assert_same_org(organization_id, org_id)
    return await service.resend(
        organization_id=organization_id,
        invitation_id=invitation_id,
        invited_by=user.id,
    )


@router.get("/invitations/preview", response_model=InvitationPreviewResponse)
async def preview_invitation(
    token: str = Query(min_length=16),
    service: InvitationService = Depends(_service),
) -> InvitationPreviewResponse:
    return await service.preview(raw_token=token)


@router.post("/invitations/accept", response_model=TokenResponse)
async def accept_invitation(
    body: AcceptInvitationRequest,
    request: Request,
    token: str = Query(min_length=16),
    service: InvitationService = Depends(_service),
) -> TokenResponse:
    return await service.accept(
        raw_token=token,
        body=body,
        user_agent=request.headers.get("user-agent"),
    )


def _assert_same_org(path_org: UUID, header_org: UUID) -> None:
    if path_org != header_org:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
