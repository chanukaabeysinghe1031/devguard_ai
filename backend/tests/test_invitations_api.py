"""Phase 5C invitation API tests (link-based; no SMTP)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _register_login(client: AsyncClient, email: str) -> tuple[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password1!",
            "full_name": "Org Owner",
            "organization_name": "Acme Workspace",
            "company_name": "Acme Ltd",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password1!"},
    )
    assert login.status_code == 200
    body = login.json()
    org_id = body["user"]["memberships"][0]["organization_id"]
    return body["access_token"], org_id


@pytest.mark.asyncio
async def test_invitation_create_preview_accept_new_user(auth_client: AsyncClient) -> None:
    token, org_id = await _register_login(auth_client, f"owner-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    create = await auth_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers=headers,
        json={"email": f"eng-{uuid4().hex[:8]}@example.com", "role": "engineer"},
    )
    assert create.status_code == 201, create.text
    payload = create.json()
    assert payload["status"] == "pending"
    assert payload["token"]
    assert "invitations/accept?token=" in payload["invite_url"]
    invite_token = payload["token"]
    invitee_email = payload["email"]

    preview = await auth_client.get(
        "/api/v1/invitations/preview",
        params={"token": invite_token},
    )
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Acme Workspace"
    assert preview.json()["user_exists"] is False

    accept = await auth_client.post(
        "/api/v1/invitations/accept",
        params={"token": invite_token},
        json={"password": "Password1!", "full_name": "Engineer One"},
    )
    assert accept.status_code == 200, accept.text
    accepted = accept.json()
    assert accepted["access_token"]
    assert any(m["organization_id"] == org_id for m in accepted["user"]["memberships"])
    assert accepted["user"]["email"] == invitee_email


@pytest.mark.asyncio
async def test_invitation_revoke_blocks_accept(auth_client: AsyncClient) -> None:
    token, org_id = await _register_login(auth_client, f"owner2-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    create = await auth_client.post(
        f"/api/v1/organizations/{org_id}/invitations",
        headers=headers,
        json={"email": f"viewer-{uuid4().hex[:8]}@example.com", "role": "viewer"},
    )
    invite_id = create.json()["id"]
    invite_token = create.json()["token"]

    revoke = await auth_client.post(
        f"/api/v1/organizations/{org_id}/invitations/{invite_id}/revoke",
        headers=headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    accept = await auth_client.post(
        "/api/v1/invitations/accept",
        params={"token": invite_token},
        json={"password": "Password1!", "full_name": "Viewer"},
    )
    assert accept.status_code in {400, 422, 409}
