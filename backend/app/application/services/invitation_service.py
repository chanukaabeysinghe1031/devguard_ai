"""Organization invitation application service (link-based; SMTP deferred — ADR-013)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.services.auth_service import AuthService, validate_password_strength
from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.domain.enums import InvitationStatus, OrganizationRole, PlatformRole
from app.domain.exceptions.auth import InvalidCredentialsError
from app.domain.exceptions.business import (
    ConflictError,
    ResourceNotFoundError,
    ValidationBusinessError,
)
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_invitation import OrganizationInvitation
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.user import User
from app.schemas.auth import TokenResponse
from app.schemas.organization import (
    AcceptInvitationRequest,
    CreateInvitationRequest,
    InvitationCreatedResponse,
    InvitationPreviewResponse,
    InvitationResponse,
)

logger = structlog.get_logger(__name__)

_INVITABLE_ROLES = frozenset(
    {
        OrganizationRole.ORGANIZATION_ADMIN.value,
        OrganizationRole.ENGINEER.value,
        OrganizationRole.VIEWER.value,
    }
)


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _invite_url(settings: Settings, raw_token: str) -> str:
    base = settings.invitation_accept_base_url.rstrip("/")
    return f"{base}?token={raw_token}"


class InvitationService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def create(
        self,
        *,
        organization_id: UUID,
        invited_by: UUID,
        body: CreateInvitationRequest,
    ) -> InvitationCreatedResponse:
        if body.role not in _INVITABLE_ROLES:
            raise ValidationBusinessError(
                "Invitations may only grant organization_admin, engineer, or viewer."
            )
        org = await self._session.get(Organization, organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")

        email = str(body.email).strip().lower()
        existing_user = await self._session.scalar(select(User).where(User.email == email))
        if existing_user is not None:
            membership = await self._session.scalar(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == existing_user.id,
                    OrganizationMember.is_active.is_(True),
                )
            )
            if membership is not None:
                raise ConflictError("User is already an active member of this organization.")

        # Revoke prior pending invites for the same email in this org.
        prior = list(
            (
                await self._session.scalars(
                    select(OrganizationInvitation).where(
                        OrganizationInvitation.organization_id == organization_id,
                        OrganizationInvitation.email == email,
                        OrganizationInvitation.status == InvitationStatus.PENDING,
                    )
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in prior:
            row.status = InvitationStatus.REVOKED
            row.revoked_at = now

        raw_token = secrets.token_urlsafe(32)
        invite = OrganizationInvitation(
            organization_id=organization_id,
            email=email,
            role=OrganizationRole(body.role),
            token_hash=_token_hash(raw_token),
            status=InvitationStatus.PENDING,
            invited_by=invited_by,
            expires_at=now + timedelta(hours=self._settings.invitation_ttl_hours),
        )
        self._session.add(invite)
        await self._session.flush()
        logger.info(
            "organization_invitation_created",
            organization_id=str(organization_id),
            invitation_id=str(invite.id),
        )
        url = _invite_url(self._settings, raw_token)
        base = self._to_response(invite, invite_url=url).model_dump()
        return InvitationCreatedResponse(**base, token=raw_token)

    async def list_invitations(self, organization_id: UUID) -> list[InvitationResponse]:
        rows = list(
            (
                await self._session.scalars(
                    select(OrganizationInvitation)
                    .where(OrganizationInvitation.organization_id == organization_id)
                    .order_by(OrganizationInvitation.created_at.desc())
                )
            ).all()
        )
        now = datetime.now(UTC)
        for row in rows:
            if row.status == InvitationStatus.PENDING and row.expires_at <= now:
                row.status = InvitationStatus.EXPIRED
        await self._session.flush()
        return [self._to_response(row) for row in rows]

    async def revoke(self, *, organization_id: UUID, invitation_id: UUID) -> InvitationResponse:
        invite = await self._load(organization_id, invitation_id)
        if invite.status != InvitationStatus.PENDING:
            raise ValidationBusinessError("Only pending invitations can be revoked.")
        invite.status = InvitationStatus.REVOKED
        invite.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return self._to_response(invite)

    async def resend(
        self,
        *,
        organization_id: UUID,
        invitation_id: UUID,
        invited_by: UUID,
    ) -> InvitationCreatedResponse:
        invite = await self._load(organization_id, invitation_id)
        if invite.status not in {InvitationStatus.PENDING, InvitationStatus.EXPIRED}:
            raise ValidationBusinessError("Only pending or expired invitations can be resent.")
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        invite.token_hash = _token_hash(raw_token)
        invite.status = InvitationStatus.PENDING
        invite.expires_at = now + timedelta(hours=self._settings.invitation_ttl_hours)
        invite.revoked_at = None
        invite.invited_by = invited_by
        await self._session.flush()
        url = _invite_url(self._settings, raw_token)
        base = self._to_response(invite, invite_url=url).model_dump()
        return InvitationCreatedResponse(**base, token=raw_token)

    async def preview(self, *, raw_token: str) -> InvitationPreviewResponse:
        invite = await self._load_by_token(raw_token)
        org = await self._session.get(Organization, invite.organization_id)
        if org is None:
            raise ResourceNotFoundError("Organization not found.")
        user_exists = (
            await self._session.scalar(select(User.id).where(User.email == invite.email))
            is not None
        )
        expired = (
            invite.expires_at <= datetime.now(UTC) or invite.status == InvitationStatus.EXPIRED
        )
        status = (
            InvitationStatus.EXPIRED.value
            if expired and invite.status == InvitationStatus.PENDING
            else invite.status.value
        )
        return InvitationPreviewResponse(
            organization_name=org.name,
            organization_slug=org.slug,
            email=invite.email,
            role=invite.role.value,
            status=status,
            expires_at=invite.expires_at,
            is_expired=expired or invite.status != InvitationStatus.PENDING,
            user_exists=user_exists,
        )

    async def accept(
        self,
        *,
        raw_token: str,
        body: AcceptInvitationRequest,
        user_agent: str | None = None,
    ) -> TokenResponse:
        invite = await self._load_by_token(raw_token)
        if invite.status != InvitationStatus.PENDING:
            raise ValidationBusinessError("This invitation is no longer valid.")
        if invite.expires_at <= datetime.now(UTC):
            invite.status = InvitationStatus.EXPIRED
            await self._session.flush()
            raise ValidationBusinessError("This invitation has expired.")

        validate_password_strength(body.password)
        existing = await self._session.scalar(select(User).where(User.email == invite.email))
        now = datetime.now(UTC)

        if existing is None:
            if not body.full_name or not body.full_name.strip():
                raise ValidationBusinessError("full_name is required for new accounts.")
            user = User(
                email=invite.email,
                password_hash=hash_password(body.password),
                full_name=body.full_name.strip(),
                platform_role=PlatformRole.NONE,
                is_active=True,
            )
            self._session.add(user)
            await self._session.flush()
        else:
            if not verify_password(body.password, existing.password_hash):
                raise InvalidCredentialsError()
            if not existing.is_active:
                raise ValidationBusinessError("This user account is disabled.")
            user = existing
            active = await self._session.scalar(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == invite.organization_id,
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.is_active.is_(True),
                )
            )
            if active is not None:
                raise ConflictError("You are already a member of this organization.")

        membership = await self._session.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == invite.organization_id,
                OrganizationMember.user_id == user.id,
            )
        )
        if membership is None:
            membership = OrganizationMember(
                organization_id=invite.organization_id,
                user_id=user.id,
                role=invite.role,
                is_active=True,
                invited_by=invite.invited_by,
            )
            self._session.add(membership)
        else:
            membership.is_active = True
            membership.role = invite.role
            membership.invited_by = invite.invited_by

        invite.status = InvitationStatus.ACCEPTED
        invite.accepted_at = now
        invite.accepted_user_id = user.id
        await self._session.flush()

        auth = AuthService(session=self._session, settings=self._settings)
        tokens = await auth.login(email=user.email, password=body.password, user_agent=user_agent)
        logger.info(
            "organization_invitation_accepted",
            invitation_id=str(invite.id),
            user_id=str(user.id),
        )
        return tokens

    async def _load(self, organization_id: UUID, invitation_id: UUID) -> OrganizationInvitation:
        invite = await self._session.scalar(
            select(OrganizationInvitation).where(
                OrganizationInvitation.id == invitation_id,
                OrganizationInvitation.organization_id == organization_id,
            )
        )
        if invite is None:
            raise ResourceNotFoundError("Invitation not found.")
        return invite

    async def _load_by_token(self, raw_token: str) -> OrganizationInvitation:
        if not raw_token or len(raw_token) < 16:
            raise ResourceNotFoundError("Invitation not found.")
        invite = await self._session.scalar(
            select(OrganizationInvitation)
            .where(OrganizationInvitation.token_hash == _token_hash(raw_token))
            .options(selectinload(OrganizationInvitation.organization))
        )
        if invite is None:
            raise ResourceNotFoundError("Invitation not found.")
        return invite

    @staticmethod
    def _to_response(
        invite: OrganizationInvitation,
        *,
        invite_url: str | None = None,
    ) -> InvitationResponse:
        return InvitationResponse(
            id=invite.id,
            organization_id=invite.organization_id,
            email=invite.email,
            role=invite.role.value,
            status=invite.status.value,
            invited_by=invite.invited_by,
            expires_at=invite.expires_at,
            accepted_at=invite.accepted_at,
            revoked_at=invite.revoked_at,
            created_at=invite.created_at,
            invite_url=invite_url,
        )
