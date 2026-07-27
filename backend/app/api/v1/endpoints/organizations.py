"""Organization and membership endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_admin, require_org_reader
from app.application.services.organization_service import OrganizationService
from app.schemas.common import MessageResponse
from app.schemas.organization import (
    AddMembershipRequest,
    MembershipResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
    UpdateMembershipRequest,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _service(session: AsyncSession = Depends(get_session)) -> OrganizationService:
    return OrganizationService(session)


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    ctx: tuple = Depends(require_org_reader),
    service: OrganizationService = Depends(_service),
) -> OrganizationResponse:
    _, organization_id, _ = ctx
    return await service.get_current(organization_id)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    body: OrganizationUpdateRequest,
    ctx: tuple = Depends(require_org_admin),
    service: OrganizationService = Depends(_service),
) -> OrganizationResponse:
    _, org_id, _ = ctx
    if organization_id != org_id:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
    return await service.update(organization_id=organization_id, body=body)


@router.get("/{organization_id}/members", response_model=list[MembershipResponse])
async def list_members(
    organization_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: OrganizationService = Depends(_service),
) -> list[MembershipResponse]:
    _, org_id, _ = ctx
    if organization_id != org_id:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
    return await service.list_members(organization_id)


@router.post(
    "/{organization_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    organization_id: UUID,
    body: AddMembershipRequest,
    ctx: tuple = Depends(require_org_admin),
    service: OrganizationService = Depends(_service),
) -> MembershipResponse:
    _, org_id, _ = ctx
    if organization_id != org_id:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
    return await service.add_member(organization_id=organization_id, body=body)


@router.patch("/{organization_id}/members/{membership_id}", response_model=MembershipResponse)
async def update_member(
    organization_id: UUID,
    membership_id: UUID,
    body: UpdateMembershipRequest,
    ctx: tuple = Depends(require_org_admin),
    service: OrganizationService = Depends(_service),
) -> MembershipResponse:
    _, org_id, _ = ctx
    if organization_id != org_id:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
    return await service.update_member(
        organization_id=organization_id,
        membership_id=membership_id,
        role=body.role,
        is_active=body.is_active,
    )


@router.delete(
    "/{organization_id}/members/{membership_id}",
    response_model=MessageResponse,
)
async def deactivate_member(
    organization_id: UUID,
    membership_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: OrganizationService = Depends(_service),
) -> MessageResponse:
    _, org_id, _ = ctx
    if organization_id != org_id:
        from app.domain.exceptions.business import ResourceNotFoundError

        raise ResourceNotFoundError("Organization not found.")
    await service.deactivate_member(
        organization_id=organization_id,
        membership_id=membership_id,
    )
    return MessageResponse(message="Membership deactivated successfully.")
