"""Authentication application service."""

from __future__ import annotations

import hmac
import re
from datetime import UTC, datetime
from uuid import UUID

import jwt
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domain.enums import OrganizationRole, PlatformRole
from app.domain.exceptions.auth import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserDisabledError,
    WeakPasswordError,
)
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.refresh_token import RefreshToken
from app.infrastructure.database.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    MembershipResponse,
    MessageResponse,
    TokenResponse,
    UserPublicResponse,
)

logger = structlog.get_logger(__name__)

_PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$")

_ROLE_RANK = {
    OrganizationRole.ORGANIZATION_OWNER: 4,
    OrganizationRole.ORGANIZATION_ADMIN: 3,
    OrganizationRole.ENGINEER: 2,
    OrganizationRole.VIEWER: 1,
}


def validate_password_strength(password: str) -> None:
    if not _PASSWORD_PATTERN.match(password):
        raise WeakPasswordError(
            "Password must be at least 8 characters and include upper, lower, and a digit."
        )


def resolve_display_role(
    platform_role: PlatformRole,
    memberships: list[OrganizationMember],
) -> str:
    """Resolve the API `role` field from platform role or strongest active membership."""
    if platform_role == PlatformRole.PLATFORM_ADMIN:
        return PlatformRole.PLATFORM_ADMIN.value

    active = [m for m in memberships if m.is_active]
    if not active:
        return PlatformRole.NONE.value

    strongest = max(active, key=lambda m: _ROLE_RANK.get(m.role, 0))
    return strongest.role.value


def user_to_public(user: User) -> UserPublicResponse:
    memberships = list(user.organization_memberships or [])
    membership_payload: list[MembershipResponse] = []
    for membership in memberships:
        organization = membership.organization
        membership_payload.append(
            MembershipResponse(
                organization_id=membership.organization_id,
                organization_slug=organization.slug if organization is not None else "",
                organization_name=organization.name if organization is not None else "",
                role=membership.role.value,
                is_active=membership.is_active,
            )
        )

    return UserPublicResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=resolve_display_role(user.platform_role, memberships),
        platform_role=user.platform_role.value,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        memberships=membership_payload,
    )


class AuthService:
    """Coordinates authentication use-cases. Never logs passwords or tokens."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def _load_user_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(
                selectinload(User.organization_memberships).selectinload(
                    OrganizationMember.organization
                )
            )
        )
        return await self._session.scalar(stmt)

    async def _load_user_by_id(self, user_id: UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.organization_memberships).selectinload(
                    OrganizationMember.organization
                )
            )
        )
        return await self._session.scalar(stmt)

    async def _issue_tokens(self, user: User, *, user_agent: str | None = None) -> TokenResponse:
        access_token, expires_in = create_access_token(subject=user.id, settings=self._settings)
        refresh_token, jti, expires_at = create_refresh_token(
            subject=user.id,
            settings=self._settings,
        )
        self._session.add(
            RefreshToken(
                user_id=user.id,
                jti=jti,
                token_hash=hash_token(refresh_token),
                expires_at=expires_at,
                user_agent=user_agent,
            )
        )
        await self._session.flush()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=user_to_public(user),
        )

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
    ) -> UserPublicResponse:
        validate_password_strength(password)
        normalized_email = email.strip().lower()
        existing = await self._load_user_by_email(normalized_email)
        if existing is not None:
            raise EmailAlreadyExistsError()

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            platform_role=PlatformRole.NONE,
            is_active=True,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)

        from app.application.services.organization_service import (
            create_default_organization_for_user,
        )

        await create_default_organization_for_user(
            self._session,
            user=user,
            full_name=full_name.strip(),
        )

        # Reload with memberships relationship populated.
        loaded = await self._load_user_by_id(user.id)
        assert loaded is not None
        logger.info("user_registered", user_id=str(loaded.id))
        return user_to_public(loaded)

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
    ) -> TokenResponse:
        user = await self._load_user_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            logger.info("login_failed")
            raise InvalidCredentialsError()
        if not user.is_active:
            logger.info("login_disabled_user", user_id=str(user.id))
            raise UserDisabledError()

        user.last_login_at = datetime.now(UTC)
        await self._session.flush()
        tokens = await self._issue_tokens(user, user_agent=user_agent)
        logger.info("login_succeeded", user_id=str(user.id))
        return tokens

    async def refresh(self, *, refresh_token: str) -> AccessTokenResponse:
        try:
            payload = decode_token(
                refresh_token,
                settings=self._settings,
                expected_type="refresh",
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        jti = str(payload["jti"])
        user_id = UUID(str(payload["sub"]))
        stored = await self._session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
        if stored is None or stored.revoked_at is not None:
            raise InvalidTokenError()
        if stored.user_id != user_id:
            raise InvalidTokenError()
        if stored.expires_at <= datetime.now(UTC):
            raise InvalidTokenError()
        if not hmac_compare(stored.token_hash, hash_token(refresh_token)):
            raise InvalidTokenError()

        user = await self._load_user_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()

        # Rotate refresh token.
        new_refresh, new_jti, new_expires = create_refresh_token(
            subject=user.id,
            settings=self._settings,
        )
        stored.revoked_at = datetime.now(UTC)
        stored.replaced_by_jti = new_jti
        self._session.add(
            RefreshToken(
                user_id=user.id,
                jti=new_jti,
                token_hash=hash_token(new_refresh),
                expires_at=new_expires,
                user_agent=stored.user_agent,
            )
        )
        access_token, expires_in = create_access_token(subject=user.id, settings=self._settings)
        await self._session.flush()
        logger.info("token_refreshed", user_id=str(user.id))
        return AccessTokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=new_refresh,
        )

    async def logout(self, *, refresh_token: str, user_id: UUID) -> MessageResponse:
        try:
            payload = decode_token(
                refresh_token,
                settings=self._settings,
                expected_type="refresh",
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError() from exc

        if UUID(str(payload["sub"])) != user_id:
            raise InvalidTokenError()

        jti = str(payload["jti"])
        stored = await self._session.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
        if stored is not None and stored.user_id == user_id and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            await self._session.flush()
            logger.info("logout_succeeded", user_id=str(user_id))
        return MessageResponse(success=True, message="Logged out successfully.")

    async def me(self, *, user_id: UUID) -> UserPublicResponse:
        user = await self._load_user_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        return user_to_public(user)

    async def change_password(
        self,
        *,
        user_id: UUID,
        current_password: str,
        new_password: str,
    ) -> MessageResponse:
        validate_password_strength(new_password)
        user = await self._load_user_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError()
        user.password_hash = hash_password(new_password)
        # Revoke all refresh sessions after password change.
        tokens = (
            await self._session.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            )
        ).all()
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
        await self._session.flush()
        logger.info("password_changed", user_id=str(user_id))
        return MessageResponse(success=True, message="Password changed successfully.")


def hmac_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
