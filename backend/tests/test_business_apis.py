"""Module 4 business API integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _register_and_login(auth_client: AsyncClient, email: str) -> tuple[str, str]:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "Business Tester",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


@pytest.mark.asyncio
async def test_register_creates_default_organization(auth_client) -> None:
    email = f"org-{uuid4().hex[:8]}@example.com"
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "Org Owner",
        },
    )
    assert response.status_code == 201
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    token = login.json()["access_token"]
    me = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    memberships = me.json()["memberships"]
    assert len(memberships) == 1
    assert memberships[0]["role"] == "organization_owner"


@pytest.mark.asyncio
async def test_project_crud_and_archive(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"proj-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    create = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Customer Portal",
            "key": "CP",
            "description": "Test project",
            "ci_provider": "github_actions",
            "cloud_provider": "aws",
            "default_environment": "production",
        },
    )
    assert create.status_code == 201, create.text
    project_id = create.json()["id"]

    listed = await auth_client.get("/api/v1/projects", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total_items"] == 1

    detail = await auth_client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["statistics"]["total_pipeline_runs"] == 0

    archived = await auth_client.post(f"/api/v1/projects/{project_id}/archive", headers=headers)
    assert archived.status_code == 200


@pytest.mark.asyncio
async def test_pipeline_run_and_incident_lifecycle(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"inc-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "API", "key": "API", "ci_provider": "github_actions"},
    )
    project_id = project.json()["id"]

    run = await auth_client.post(
        f"/api/v1/projects/{project_id}/pipeline-runs",
        headers=headers,
        json={
            "external_run_id": "485",
            "provider": "github_actions",
            "workflow_name": "Deploy",
            "branch": "main",
            "status": "failed",
        },
    )
    assert run.status_code == 201
    run_id = run.json()["id"]

    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project_id,
            "pipeline_run_id": run_id,
            "title": "Deploy failed",
            "source": "manual_upload",
            "severity": "critical",
            "priority": "urgent",
            "environment": "production",
        },
    )
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    assert incident.json()["incident_number"].startswith("INC-")

    status_change = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "open", "comment": "Ready for triage"},
    )
    assert status_change.status_code == 200

    invalid = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/status",
        headers=headers,
        json={"status": "closed"},
    )
    assert invalid.status_code == 409

    timeline = await auth_client.get(
        f"/api/v1/incidents/{incident_id}/timeline",
        headers=headers,
    )
    assert timeline.status_code == 200
    assert len(timeline.json()["items"]) >= 2


@pytest.mark.asyncio
async def test_incident_note_and_resolution(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"note-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Notes", "key": "NT", "ci_provider": "github_actions"},
    )
    project_id = project.json()["id"]

    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project_id,
            "title": "Failure",
            "source": "manual_upload",
            "severity": "high",
        },
    )
    incident_id = incident.json()["id"]

    note = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers=headers,
        json={"note_type": "investigation", "content": "Checking IAM policy"},
    )
    assert note.status_code == 201
    note_id = note.json()["id"]

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
        json={
            "resolution_summary": "Fixed IAM",
            "confirmed_root_cause": "Missing permission",
            "resolution_steps": ["Updated policy"],
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    patched = await auth_client.patch(
        f"/api/v1/notes/{note_id}",
        headers=headers,
        json={"content": "Updated note"},
    )
    assert patched.status_code == 200


@pytest.mark.asyncio
async def test_analysis_run_initiation_executes_pipeline(auth_client) -> None:
    token, org_id = await _register_and_login(auth_client, f"ana-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "AI", "key": "AI", "ci_provider": "github_actions"},
    )
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Need analysis",
            "source": "manual_upload",
            "severity": "medium",
        },
    )
    incident_id = incident.json()["id"]

    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[
            (
                "files",
                (
                    "deploy.log",
                    b"ERROR: User is not authorized to perform: s3:PutObject\nAccessDenied\n",
                    "text/plain",
                ),
            )
        ],
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["files"][0]["id"]

    analysis = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={"analysis_type": "full", "file_ids": [file_id]},
    )
    assert analysis.status_code == 202, analysis.text
    run_id = analysis.json()["analysis_run_id"]
    # Sync execution mode completes within the request.
    assert analysis.json()["status"] == "completed"
    assert analysis.json()["progress_percentage"] == 100

    status = await auth_client.get(f"/api/v1/analyses/{run_id}/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["stages"]


@pytest.mark.asyncio
async def test_cross_organization_access_denied(
    auth_client,
    repository_db_session: AsyncSession,
) -> None:
    owner_email = f"owner-{uuid4().hex[:8]}@example.com"
    outsider_email = f"outsider-{uuid4().hex[:8]}@example.com"

    owner_token, org_id = await _register_and_login(auth_client, owner_email)
    await _register_and_login(auth_client, outsider_email)
    outsider_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": outsider_email, "password": "SecurePassword123!"},
    )
    outsider_token = outsider_login.json()["access_token"]

    owner_headers = {"Authorization": f"Bearer {owner_token}", "X-Organization-Id": org_id}
    project = await auth_client.post(
        "/api/v1/projects",
        headers=owner_headers,
        json={"name": "Private", "key": "PRV", "ci_provider": "github_actions"},
    )
    project_id = project.json()["id"]

    denied = await auth_client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {outsider_token}", "X-Organization-Id": org_id},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_last_owner_protection(auth_client, repository_db_session: AsyncSession) -> None:
    token, org_id = await _register_and_login(auth_client, f"own-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    members = await auth_client.get(f"/api/v1/organizations/{org_id}/members", headers=headers)
    membership_id = members.json()[0]["id"]

    demote = await auth_client.patch(
        f"/api/v1/organizations/{org_id}/members/{membership_id}",
        headers=headers,
        json={"role": "engineer"},
    )
    assert demote.status_code == 409
    assert demote.json()["error_code"] == "LAST_OWNER_PROTECTED"
