"""Incident report API integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _auth(auth_client: AsyncClient) -> dict[str, str]:
    email = f"rep_{uuid4().hex[:8]}@example.com"
    await auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Report Tester"},
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    org_id = body["user"]["memberships"][0]["organization_id"]
    return {"Authorization": f"Bearer {body['access_token']}", "X-Organization-Id": org_id}


@pytest.mark.asyncio
async def test_generate_list_and_download_report(auth_client) -> None:
    headers = await _auth(auth_client)

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Report Proj",
            "key": f"R{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    assert project.status_code == 201

    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Report incident",
            "description": "Needs report",
            "source": "manual_upload",
            "severity": "low",
        },
    )
    assert incident.status_code == 201
    incident_id = incident.json()["id"]

    await auth_client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers=headers,
        json={"note_type": "investigation", "content": "Initial triage note"},
    )

    generated = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/reports",
        headers=headers,
        json={"format": "json", "include_timeline": True, "include_resolution": True},
    )
    assert generated.status_code == 201, generated.text
    gen_body = generated.json()
    assert gen_body["generation_status"] == "completed"
    report_id = gen_body["report_id"]

    listed = await auth_client.get("/api/v1/reports", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total_items"] >= 1

    detail = await auth_client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["format"] == "json"
    assert detail_body["content"] is not None
    assert detail_body["content"]["incident"]["id"] == incident_id
    assert detail_body["download_url"].endswith(f"/reports/{report_id}/download")

    download = await auth_client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert download.status_code == 200
    assert b"Report incident" in download.content


@pytest.mark.asyncio
async def test_history_lists_resolved_incidents(auth_client) -> None:
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
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Historical incident",
            "source": "manual_upload",
            "severity": "medium",
        },
    )
    incident_id = incident.json()["id"]
    await auth_client.post(
        f"/api/v1/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "open"},
    )
    await auth_client.post(
        f"/api/v1/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "in_progress"},
    )
    resolved = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/resolve",
        headers=headers,
        json={"resolution_summary": "Fixed configuration", "confirmed_root_cause": "Bad config"},
    )
    assert resolved.status_code == 200

    history = await auth_client.get("/api/v1/history/incidents", headers=headers)
    assert history.status_code == 200, history.text
    items = history.json()["items"]
    assert any(item["id"] == incident_id for item in items)
    match = next(item for item in items if item["id"] == incident_id)
    assert match["resolution_summary"] == "Fixed configuration"
    assert match["resolved_at"] is not None
