"""Authentication and authorization FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_session, get_settings_dep
from app.core.config import Settings
from app.core.security import decode_token
from app.domain.enums import OrganizationRole, PlatformRole
from app.domain.exceptions.auth import (
    AuthorizationError,
    InvalidTokenError,
    MembershipInactiveError,
    UserDisabledError,
)
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.user import User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Principal resolved from a valid access token."""

    id: UUID
    email: str
    full_name: str
    platform_role: PlatformRole
    is_active: bool
    user: User


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidTokenError("Authentication required.")

    try:
        payload = decode_token(
            credentials.credentials,
            settings=settings,
            expected_type="access",
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    user_id = UUID(str(payload["sub"]))
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.organization_memberships).selectinload(
                OrganizationMember.organization
            )
        )
    )
    user = await session.scalar(stmt)
    if user is None:
        raise InvalidTokenError()
    if not user.is_active:
        raise UserDisabledError()

    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        platform_role=user.platform_role,
        is_active=user.is_active,
        user=user,
    )


def require_platform_admin(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if current_user.platform_role != PlatformRole.PLATFORM_ADMIN:
        raise AuthorizationError()
    return current_user


async def resolve_organization_membership(
    *,
    session: AsyncSession,
    user_id: UUID,
    organization_id: UUID,
) -> OrganizationMember:
    membership = await session.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if membership is None:
        raise AuthorizationError("Organization membership is required.")
    if not membership.is_active:
        raise MembershipInactiveError()
    return membership


def require_organization_roles(
    *allowed_roles: OrganizationRole,
) -> Callable[..., Awaitable[AuthenticatedUser]]:
    """Depend on X-Organization-Id header and enforce membership role."""

    async def _dependency(
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
        x_organization_id: UUID | None = Header(default=None, alias="X-Organization-Id"),
    ) -> AuthenticatedUser:
        if current_user.platform_role == PlatformRole.PLATFORM_ADMIN:
            return current_user
        if x_organization_id is None:
            raise AuthorizationError("X-Organization-Id header is required.")

        membership = await resolve_organization_membership(
            session=session,
            user_id=current_user.id,
            organization_id=x_organization_id,
        )
        if allowed_roles and membership.role not in allowed_roles:
            raise AuthorizationError()
        return current_user

    return _dependency


async def require_project_organization_access(
    *,
    session: AsyncSession,
    current_user: AuthenticatedUser,
    project_id: UUID,
    allowed_roles: tuple[OrganizationRole, ...] | None = None,
) -> Project:
    """Load a project and ensure the caller may access its organization."""
    project = await session.get(Project, project_id)
    if project is None:
        raise AuthorizationError("Project not found or inaccessible.")

    if current_user.platform_role == PlatformRole.PLATFORM_ADMIN:
        return project

    membership = await resolve_organization_membership(
        session=session,
        user_id=current_user.id,
        organization_id=project.organization_id,
    )
    if allowed_roles and membership.role not in allowed_roles:
        raise AuthorizationError()
    return project
