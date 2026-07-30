"""Notification API integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _auth(auth_client: AsyncClient) -> dict[str, str]:
    email = f"notif_{uuid4().hex[:8]}@example.com"
    await auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Notif Tester"},
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    org_id = body["user"]["memberships"][0]["organization_id"]
    return {"Authorization": f"Bearer {body['access_token']}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_notifications_lifecycle_via_assignment(auth_client) -> None:
    headers = await _auth(auth_client)

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Notif Proj",
            "key": f"N{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    assert project.status_code == 201

    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Notify me",
            "source": "manual_upload",
            "severity": "high",
        },
    )
    assert incident.status_code == 201
    incident_id = incident.json()["id"]

    me = await auth_client.get("/api/v1/auth/me", headers=headers)
    user_id = me.json()["id"]

    assigned = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/assign",
        headers=headers,
        json={"user_id": user_id, "reason": "Self assign for test"},
    )
    assert assigned.status_code == 200

    listed = await auth_client.get("/api/v1/notifications", headers=headers)
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["total_items"] >= 1
    assert payload["unread_count"] >= 1
    notification_id = payload["items"][0]["id"]

    read = await auth_client.post(
        f"/api/v1/notifications/{notification_id}/read",
        headers=headers,
    )
    assert read.status_code == 200
    assert read.json()["is_read"] is True

    read_all = await auth_client.post("/api/v1/notifications/read-all", headers=headers)
    assert read_all.status_code == 200

    unread = await auth_client.get("/api/v1/notifications?is_read=false", headers=headers)
    assert unread.status_code == 200
    assert unread.json()["total_items"] == 0

    deleted = await auth_client.delete(
        f"/api/v1/notifications/{notification_id}",
        headers=headers,
    )
    assert deleted.status_code == 204

    after_delete = await auth_client.get("/api/v1/notifications", headers=headers)
    assert after_delete.status_code == 200
    ids = {item["id"] for item in after_delete.json()["items"]}
    assert notification_id not in ids


@pytest.mark.asyncio
async def test_notifications_from_analysis_complete(auth_client) -> None:
    headers = await _auth(auth_client)

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Analysis Notif",
            "key": f"A{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Analysis notify",
            "source": "manual_upload",
            "severity": "medium",
        },
    )
    incident_id = incident.json()["id"]
    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("fail.log", b"AccessDenied not authorized\n", "text/plain"))],
    )
    assert upload.status_code == 201
    file_id = upload.json()["files"][0]["id"]

    started = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={
            "analysis_type": "full",
            "file_ids": [file_id],
            "options": {"enable_rag": False, "enable_llm": False, "execution_mode": "rules_only"},
        },
    )
    assert started.status_code in {200, 202}, started.text

    listed = await auth_client.get(
        "/api/v1/notifications?notification_type=analysis_completed",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total_items"] >= 1
