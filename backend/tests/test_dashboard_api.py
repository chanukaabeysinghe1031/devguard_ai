"""Dashboard API integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _auth(auth_client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"dash_{uuid4().hex[:8]}@example.com"
    await auth_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "full_name": "Dash Tester"},
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    org_id = body["user"]["memberships"][0]["organization_id"]
    headers = {"Authorization": f"Bearer {body['access_token']}", "X-Organization-Id": org_id}
    return headers, org_id


@pytest.mark.asyncio
async def test_dashboard_summary_and_recent(auth_client) -> None:
    headers, _ = await _auth(auth_client)

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Dash Proj",
            "key": f"D{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    run = await auth_client.post(
        f"/api/v1/projects/{project_id}/pipeline-runs",
        headers=headers,
        json={
            "external_run_id": "100",
            "provider": "github_actions",
            "workflow_name": "Deploy",
            "status": "failed",
        },
    )
    assert run.status_code == 201

    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project_id,
            "pipeline_run_id": run.json()["id"],
            "title": "Dashboard incident",
            "source": "manual_upload",
            "severity": "critical",
        },
    )
    assert incident.status_code == 201

    summary = await auth_client.get("/api/v1/dashboard/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["open_incidents"] >= 1
    assert body["critical_incidents"] >= 1
    assert "failed_deployments" in body
    assert "deployment_success_rate" in body

    recent = await auth_client.get("/api/v1/dashboard/recent-incidents?limit=5", headers=headers)
    assert recent.status_code == 200
    assert len(recent.json()["items"]) >= 1

    severity = await auth_client.get("/api/v1/dashboard/severity-distribution", headers=headers)
    assert severity.status_code == 200
    assert severity.json()["critical"] >= 1

    activity = await auth_client.get("/api/v1/dashboard/activity?limit=5", headers=headers)
    assert activity.status_code == 200
    assert len(activity.json()["items"]) >= 1

    trend = await auth_client.get("/api/v1/dashboard/incident-trend?interval=day", headers=headers)
    assert trend.status_code == 200
    assert trend.json()["interval"] == "day"

    categories = await auth_client.get("/api/v1/dashboard/failure-categories", headers=headers)
    assert categories.status_code == 200
    assert "items" in categories.json()

    active = await auth_client.get("/api/v1/dashboard/active-analyses", headers=headers)
    assert active.status_code == 200
    assert "items" in active.json()
