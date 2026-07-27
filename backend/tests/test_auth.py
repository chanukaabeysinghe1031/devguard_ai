"""Authentication and authorization API tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.deps.auth import (
    AuthenticatedUser,
    require_organization_roles,
    require_platform_admin,
    resolve_organization_membership,
)
from app.core.security import hash_password, verify_password
from app.domain.enums import OrganizationRole, PlatformRole
from app.domain.exceptions.auth import AuthorizationError, MembershipInactiveError
from app.infrastructure.database.models.organization import Organization
from app.infrastructure.database.models.organization_member import OrganizationMember
from app.infrastructure.database.models.refresh_token import RefreshToken
from app.infrastructure.database.models.user import User


@pytest.mark.asyncio
async def test_password_hash_never_stores_plaintext() -> None:
    password = "SecurePassword123!"
    hashed = hash_password(password)
    assert password not in hashed
    assert verify_password(password, hashed)
    assert not verify_password("wrong-password", hashed)


@pytest.mark.asyncio
async def test_register_and_login_flow(auth_client) -> None:
    register = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "Engineer@Example.com",
            "password": "SecurePassword123!",
            "full_name": "DevOps Engineer",
        },
    )
    assert register.status_code == 201, register.text
    body = register.json()
    assert body["email"] == "engineer@example.com"
    assert "password" not in body
    assert "password_hash" not in body

    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "engineer@example.com", "password": "SecurePassword123!"},
    )
    assert login.status_code == 200, login.text
    tokens = login.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["expires_in"] > 0
    assert tokens["user"]["email"] == "engineer@example.com"


@pytest.mark.asyncio
async def test_login_invalid_credentials_is_generic(auth_client) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "SecurePassword123!",
            "full_name": "User",
        },
    )
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["error_code"] == "INVALID_CREDENTIALS"
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_rejects_disabled_user(auth_client, repository_db_session) -> None:
    user = User(
        email="disabled@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Disabled User",
        is_active=False,
    )
    repository_db_session.add(user)
    await repository_db_session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "SecurePassword123!"},
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "USER_DISABLED"


@pytest.mark.asyncio
async def test_me_requires_bearer_token(auth_client) -> None:
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(auth_client) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@example.com",
            "password": "SecurePassword123!",
            "full_name": "Me User",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "SecurePassword123!"},
    )
    token = login.json()["access_token"]
    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "me@example.com"
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_refresh_rotates_and_revokes_old_token(auth_client, repository_db_session) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "SecurePassword123!",
            "full_name": "Refresh User",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "SecurePassword123!"},
    )
    old_refresh = login.json()["refresh_token"]

    refreshed = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["refresh_token"] != old_refresh

    reuse = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reuse.status_code == 401

    tokens = (await repository_db_session.scalars(select(RefreshToken))).all()
    assert any(token.revoked_at is not None for token in tokens)


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(auth_client) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@example.com",
            "password": "SecurePassword123!",
            "full_name": "Logout User",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "SecurePassword123!"},
    )
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    logout = await auth_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": refresh},
    )
    assert logout.status_code == 200

    refresh_again = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert refresh_again.status_code == 401


@pytest.mark.asyncio
async def test_change_password_revokes_sessions(auth_client) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "pw@example.com",
            "password": "SecurePassword123!",
            "full_name": "Password User",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "pw@example.com", "password": "SecurePassword123!"},
    )
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    changed = await auth_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {access}"},
        json={
            "current_password": "SecurePassword123!",
            "new_password": "AnotherSecure123!",
        },
    )
    assert changed.status_code == 200

    refresh_again = await auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert refresh_again.status_code == 401

    login_new = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "pw@example.com", "password": "AnotherSecure123!"},
    )
    assert login_new.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_register_rejected(auth_client) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "SecurePassword123!",
        "full_name": "Dup User",
    }
    first = await auth_client.post("/api/v1/auth/register", json=payload)
    second = await auth_client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error_code"] == "EMAIL_ALREADY_EXISTS"


def _auth_user(user: User) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        platform_role=user.platform_role,
        is_active=user.is_active,
        user=user,
    )


@pytest.mark.asyncio
async def test_organization_membership_resolution_and_roles(repository_db_session) -> None:
    user = User(
        email="member@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Member",
    )
    organization = Organization(name="Acme", slug=f"acme-{uuid4().hex[:8]}")
    foreign = Organization(name="Other", slug=f"other-{uuid4().hex[:8]}")
    repository_db_session.add_all([user, organization, foreign])
    await repository_db_session.flush()
    repository_db_session.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.VIEWER,
            is_active=True,
        )
    )
    await repository_db_session.commit()

    membership = await resolve_organization_membership(
        session=repository_db_session,
        user_id=user.id,
        organization_id=organization.id,
    )
    assert membership.role == OrganizationRole.VIEWER

    with pytest.raises(AuthorizationError):
        await resolve_organization_membership(
            session=repository_db_session,
            user_id=user.id,
            organization_id=foreign.id,
        )

    dependency = require_organization_roles(
        OrganizationRole.ENGINEER,
        OrganizationRole.ORGANIZATION_ADMIN,
    )
    with pytest.raises(AuthorizationError):
        await dependency(
            current_user=_auth_user(user),
            session=repository_db_session,
            x_organization_id=organization.id,
        )

    membership.role = OrganizationRole.ENGINEER
    await repository_db_session.commit()

    allowed = await dependency(
        current_user=_auth_user(user),
        session=repository_db_session,
        x_organization_id=organization.id,
    )
    assert allowed.id == user.id


@pytest.mark.asyncio
async def test_platform_admin_bypasses_org_role_checks(repository_db_session) -> None:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Platform Admin",
        platform_role=PlatformRole.PLATFORM_ADMIN,
    )
    repository_db_session.add(admin)
    await repository_db_session.commit()

    principal = require_platform_admin(_auth_user(admin))
    assert principal.platform_role == PlatformRole.PLATFORM_ADMIN

    dependency = require_organization_roles(OrganizationRole.ORGANIZATION_OWNER)
    allowed = await dependency(
        current_user=_auth_user(admin),
        session=repository_db_session,
        x_organization_id=None,
    )
    assert allowed.id == admin.id


@pytest.mark.asyncio
async def test_inactive_membership_is_rejected(repository_db_session) -> None:
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Inactive",
    )
    organization = Organization(name="Inactive Org", slug=f"inactive-{uuid4().hex[:8]}")
    repository_db_session.add_all([user, organization])
    await repository_db_session.flush()
    repository_db_session.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=OrganizationRole.ENGINEER,
            is_active=False,
        )
    )
    await repository_db_session.commit()

    with pytest.raises(MembershipInactiveError):
        await resolve_organization_membership(
            session=repository_db_session,
            user_id=user.id,
            organization_id=organization.id,
        )


@pytest.mark.asyncio
async def test_require_platform_admin_rejects_engineer(repository_db_session) -> None:
    user = User(
        email="eng@example.com",
        password_hash=hash_password("SecurePassword123!"),
        full_name="Engineer",
        platform_role=PlatformRole.NONE,
    )
    repository_db_session.add(user)
    await repository_db_session.commit()

    with pytest.raises(AuthorizationError):
        require_platform_admin(_auth_user(user))
