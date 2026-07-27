"""Organization and membership application service."""

from __future__ import annotations

import re
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import membership_to_response, organization_to_response
from app.domain.enums import OrganizationRole
from app.domain.exceptions.business import (
    ConflictError,
    LastOwnerProtectionError,
    ResourceNotFoundError,
    ValidationBusinessError,
)
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.user import User
from app.schemas.organization import (
    AddMembershipRequest,
    MembershipResponse,
    OrganizationResponse,
    OrganizationUpdateRequest,
)

logger = structlog.get_logger(__name__)

_VALID_ROLES = frozenset(role.value for role in OrganizationRole)


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_current(self, organization_id: UUID) -> OrganizationResponse:
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")
        return organization_to_response(org)

    async def update(
        self,
        *,
        organization_id: UUID,
        body: OrganizationUpdateRequest,
    ) -> OrganizationResponse:
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")
        if body.name is not None:
            org.name = body.name.strip()
        await self._session.flush()
        logger.info("organization_updated", organization_id=str(organization_id))
        return organization_to_response(org)

    async def list_members(self, organization_id: UUID) -> list[MembershipResponse]:
        stmt = (
            select(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(OrganizationMember.joined_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [membership_to_response(member, user) for member, user in rows]

    async def add_member(
        self,
        *,
        organization_id: UUID,
        body: AddMembershipRequest,
    ) -> MembershipResponse:
        if body.role not in _VALID_ROLES:
            raise ValidationBusinessError(f"Invalid role '{body.role}'.")
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")

        email = str(body.email).strip().lower()
        user = await self._session.scalar(select(User).where(User.email == email))
        if user is None:
            raise ResourceNotFoundError("User not found.")

        existing = await self._session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        if existing is not None:
            if existing.is_active:
                raise ConflictError("User is already a member of this organization.")
            existing.is_active = True
            existing.role = OrganizationRole(body.role)
            member = existing
        else:
            member = OrganizationMember(
                organization_id=organization_id,
                user_id=user.id,
                role=OrganizationRole(body.role),
                is_active=True,
            )
            self._session.add(member)

        await self._session.flush()
        logger.info("membership_added", organization_id=str(organization_id), user_id=str(user.id))
        return membership_to_response(member, user)

    async def update_member(
        self,
        *,
        organization_id: UUID,
        membership_id: UUID,
        role: str | None,
        is_active: bool | None,
    ) -> MembershipResponse:
        member = await self._load_membership(organization_id, membership_id)
        user = await self._session.get(User, member.user_id)
        assert user is not None

        if role is not None:
            if role not in _VALID_ROLES:
                raise ValidationBusinessError(f"Invalid role '{role}'.")
            await self._guard_last_owner(member, new_role=OrganizationRole(role))
            member.role = OrganizationRole(role)

        if is_active is not None:
            if not is_active:
                await self._guard_last_owner(member, deactivate=True)
            member.is_active = is_active

        await self._session.flush()
        return membership_to_response(member, user)

    async def deactivate_member(
        self,
        *,
        organization_id: UUID,
        membership_id: UUID,
    ) -> None:
        member = await self._load_membership(organization_id, membership_id)
        await self._guard_last_owner(member, deactivate=True)
        member.is_active = False
        await self._session.flush()
        logger.info("membership_deactivated", membership_id=str(membership_id))

    async def _load_membership(
        self,
        organization_id: UUID,
        membership_id: UUID,
    ) -> OrganizationMember:
        member = await self._session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.id == membership_id,
                OrganizationMember.organization_id == organization_id,
            )
        )
        if member is None:
            raise ResourceNotFoundError("Membership not found.")
        return member

    async def _guard_last_owner(
        self,
        member: OrganizationMember,
        *,
        new_role: OrganizationRole | None = None,
        deactivate: bool = False,
    ) -> None:
        if member.role != OrganizationRole.ORGANIZATION_OWNER or not member.is_active:
            return
        demoting = new_role is not None and new_role != OrganizationRole.ORGANIZATION_OWNER
        if not demoting and not deactivate:
            return

        count = await self._session.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(
                OrganizationMember.organization_id == member.organization_id,
                OrganizationMember.role == OrganizationRole.ORGANIZATION_OWNER,
                OrganizationMember.is_active.is_(True),
            )
        )
        if (count or 0) <= 1:
            raise LastOwnerProtectionError()


async def create_default_organization_for_user(
    session: AsyncSession,
    *,
    user: User,
    full_name: str,
) -> OrganizationMember:
    """Create a default organization and owner membership on registration."""
    base_slug = _slugify(full_name or user.email.split("@")[0])
    slug = base_slug
    suffix = 1
    while await session.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    org = Organization(name=f"{full_name.strip()}'s Organization", slug=slug)
    session.add(org)
    await session.flush()
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationRole.ORGANIZATION_OWNER,
        is_active=True,
    )
    session.add(membership)
    await session.flush()
    return membership


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "organization"
