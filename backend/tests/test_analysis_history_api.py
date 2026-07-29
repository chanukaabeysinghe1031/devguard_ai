"""Regression: incident analysis listing supports diagnosis history reload."""

from __future__ import annotations

from uuid import uuid4

import pytest


async def _auth(auth_client):
    email = f"hist_{uuid4().hex[:8]}@example.com"
    await auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Hist"},
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    token = body["access_token"]
    org_id = body["user"]["memberships"][0]["organization_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    return headers


@pytest.mark.asyncio
async def test_list_incident_analyses_for_history_reload(auth_client) -> None:
    headers = await _auth(auth_client)
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Hist Proj",
            "key": f"H{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    assert project.status_code == 201, project.text
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "History incident",
            "source": "manual_upload",
            "severity": "low",
        },
    )
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", ("hist.log", b"AccessDenied not authorized sts:AssumeRole\n", "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["files"][0]["id"]
    started = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={
            "analysis_type": "full",
            "file_ids": [file_id],
            "options": {
                "enable_rag": False,
                "enable_llm": False,
                "execution_mode": "rules_only",
            },
        },
    )
    assert started.status_code in {200, 202}, started.text
    listed = await auth_client.get(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    assert rows[0]["id"]
    assert rows[0]["status"] in {"completed", "queued", "running", "failed"}
