"""End-to-end GitHub Actions ingestion API tests (Phase 5B, ADR-005).

Uses the deterministic fake provider and synchronous delivery processing so the
resulting pipeline run, incident, and analysis are observable in-request.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.infrastructure.integrations.fake_github_provider import (
    FAKE_INSTALLATION_ID,
    FAKE_REPOSITORY_FULL_NAME,
    FAKE_REPOSITORY_ID,
)

WEBHOOK_URL = "/api/v1/integrations/github/webhook"
WEBHOOK_SECRET = "test-secret"


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _workflow_run_payload(
    *,
    run_id: int,
    conclusion: str = "failure",
    branch: str = "main",
    workflow_name: str = "CI",
    repository_id: int = FAKE_REPOSITORY_ID,
) -> bytes:
    return json.dumps(
        {
            "action": "completed",
            "installation": {
                "id": FAKE_INSTALLATION_ID,
                "account": {"login": "devguard-fixtures"},
            },
            "repository": {
                "id": repository_id,
                "full_name": FAKE_REPOSITORY_FULL_NAME,
                "default_branch": "main",
            },
            "workflow_run": {
                "id": run_id,
                "name": workflow_name,
                "workflow_id": 1,
                "run_number": 41,
                "run_attempt": 1,
                "event": "push",
                "status": "completed",
                "conclusion": conclusion,
                "head_branch": branch,
                "head_sha": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
                "html_url": (
                    f"https://github.com/{FAKE_REPOSITORY_FULL_NAME}/actions/runs/{run_id}"
                ),
                "run_started_at": "2026-07-30T10:14:00Z",
                "updated_at": "2026-07-30T10:16:00Z",
                "actor_login": "octocat",
            },
        }
    ).encode("utf-8")


async def _post_webhook(
    client: AsyncClient,
    body: bytes,
    *,
    delivery_id: str,
    event: str = "workflow_run",
    signature: str | None = None,
):
    return await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature if signature is not None else _sign(body),
        },
    )


async def _register_owner(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"gh-{uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassw0rd!",
            "full_name": "GitHub Owner",
            "organization_name": "GitHub Test Org",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassw0rd!"},
    )
    body = login.json()
    organization_id = body["user"]["memberships"][0]["organization_id"]
    headers = {
        "Authorization": f"Bearer {body['access_token']}",
        "X-Organization-Id": organization_id,
    }
    return headers, organization_id


async def _create_project(client: AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "Demo Service",
            "key": f"DS{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
            "default_branch": "main",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _connect_repository(
    client: AsyncClient,
    headers: dict[str, str],
    project_id: str,
    **overrides,
) -> dict:
    install_url = await client.post(
        "/api/v1/integrations/github/install-url",
        headers=headers,
        json={"project_id": project_id},
    )
    assert install_url.status_code == 200, install_url.text
    state = install_url.json()["state"]

    setup = await client.post(
        "/api/v1/integrations/github/setup",
        headers=headers,
        json={"installation_id": FAKE_INSTALLATION_ID, "state": state},
    )
    assert setup.status_code == 200, setup.text
    installation_row_id = setup.json()["installation"]["id"]

    payload = {
        "installation_id": installation_row_id,
        "github_repository_id": FAKE_REPOSITORY_ID,
        "repository_full_name": FAKE_REPOSITORY_FULL_NAME,
        "default_branch": "main",
    }
    payload.update(overrides)
    connect = await client.post(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=headers,
        json=payload,
    )
    assert connect.status_code == 201, connect.text
    return connect.json()


@pytest.mark.asyncio
async def test_signed_failure_webhook_creates_pipeline_run_and_incident(
    auth_client: AsyncClient,
) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    run_id = 5550001
    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=run_id),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202, response.text
    assert response.json()["ok"] is True
    assert response.json()["duplicate"] is False

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id, "source": "github_webhook"},
    )
    assert incidents.status_code == 200, incidents.text
    items = incidents.json()["items"]
    assert len(items) == 1
    assert FAKE_REPOSITORY_FULL_NAME in items[0]["title"]

    detail = await auth_client.get(f"/api/v1/incidents/{items[0]['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    incident = detail.json()
    assert incident["source"] == "github_webhook"
    assert incident["severity"] == "medium"
    assert incident["pipeline_run_id"] is not None

    runs = await auth_client.get(
        f"/api/v1/projects/{project_id}/pipeline-runs",
        headers=headers,
    )
    assert runs.status_code == 200, runs.text
    run_items = runs.json()["items"]
    assert len(run_items) == 1
    assert run_items[0]["external_run_id"] == str(run_id)
    assert run_items[0]["provider"] == "github_actions"


@pytest.mark.asyncio
async def test_ingestion_stores_logs_and_starts_analysis(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550002),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    incident_id = incidents.json()["items"][0]["id"]

    files = await auth_client.get(f"/api/v1/incidents/{incident_id}/files", headers=headers)
    assert files.status_code == 200, files.text
    assert len(files.json()["items"]) >= 1

    analyses = await auth_client.get(f"/api/v1/incidents/{incident_id}/analyses", headers=headers)
    assert analyses.status_code == 200, analyses.text
    assert len(analyses.json()) == 1

    timeline = await auth_client.get(f"/api/v1/incidents/{incident_id}/timeline", headers=headers)
    assert timeline.status_code == 200, timeline.text
    events = timeline.json()["items"]
    system_events = [event for event in events if event["actor_type"] == "system"]
    assert {"incident_created", "file_uploaded", "analysis_queued"} <= {
        event["event_type"] for event in system_events
    }


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_create_second_incident(
    auth_client: AsyncClient,
) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    delivery_id = f"delivery-{uuid4().hex[:12]}"
    body = _workflow_run_payload(run_id=5550003)

    first = await _post_webhook(auth_client, body, delivery_id=delivery_id)
    assert first.json()["duplicate"] is False
    second = await _post_webhook(auth_client, body, delivery_id=delivery_id)
    assert second.status_code == 202
    assert second.json()["duplicate"] is True

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    assert len(incidents.json()["items"]) == 1


@pytest.mark.asyncio
async def test_redelivered_run_under_new_delivery_id_reuses_pipeline_run(
    auth_client: AsyncClient,
) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    body = _workflow_run_payload(run_id=5550004)
    await _post_webhook(auth_client, body, delivery_id=f"delivery-{uuid4().hex[:12]}")
    await _post_webhook(auth_client, body, delivery_id=f"delivery-{uuid4().hex[:12]}")

    runs = await auth_client.get(
        f"/api/v1/projects/{project_id}/pipeline-runs",
        headers=headers,
    )
    assert len(runs.json()["items"]) == 1
    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    assert len(incidents.json()["items"]) == 1


@pytest.mark.asyncio
async def test_successful_conclusion_is_ignored(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550005, conclusion="success"),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202
    assert response.json()["processing_status"] == "ignored"

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    assert incidents.json()["items"] == []

    activity = await auth_client.get(
        f"/api/v1/projects/{project_id}/integrations/github/activity",
        headers=headers,
    )
    assert activity.status_code == 200, activity.text
    items = activity.json()["items"]
    assert len(items) == 1
    assert items[0]["processing_status"] == "ignored"
    assert items[0]["error_code"] == "conclusion_not_failure"


@pytest.mark.asyncio
async def test_branch_filter_ignores_non_matching_branch(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(
        auth_client,
        headers,
        project_id,
        branch_filters={"mode": "patterns", "patterns": ["release/*"]},
    )

    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550006, branch="feature/login"),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.json()["processing_status"] == "ignored"

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    assert incidents.json()["items"] == []


@pytest.mark.asyncio
async def test_paused_connection_ignores_deliveries(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    paused = await auth_client.post(
        f"/api/v1/projects/{project_id}/integrations/github/pause",
        headers=headers,
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["is_paused"] is True

    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550007),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.json()["processing_status"] == "ignored"

    incidents = await auth_client.get(
        "/api/v1/incidents",
        headers=headers,
        params={"project_id": project_id},
    )
    assert incidents.json()["items"] == []


@pytest.mark.asyncio
async def test_unknown_repository_is_ignored(auth_client: AsyncClient) -> None:
    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550008, repository_id=111222333),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202
    assert response.json()["processing_status"] == "ignored"


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected(auth_client: AsyncClient) -> None:
    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=5550009),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
        signature="sha256=deadbeef",
    )
    assert response.status_code in (401, 403)
    assert response.json()["error_code"] == "WEBHOOK_SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_missing_signature_header_is_rejected(auth_client: AsyncClient) -> None:
    body = _workflow_run_payload(run_id=5550010)
    response = await auth_client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "workflow_run",
            "X-GitHub-Delivery": f"delivery-{uuid4().hex[:12]}",
        },
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_webhook_requires_no_jwt(auth_client: AsyncClient) -> None:
    """The webhook route must not be behind bearer authentication."""
    response = await auth_client.post(
        WEBHOOK_URL,
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "ping",
            "X-GitHub-Delivery": "ping-1",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
    )
    # Rejected for signature, not for a missing bearer token.
    assert response.status_code in (401, 403)
    assert response.json()["error_code"] == "WEBHOOK_SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_project_integration_listing_and_lifecycle(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    connection = await _connect_repository(auth_client, headers, project_id)
    assert connection["auto_create_incidents"] is True

    listing = await auth_client.get(
        f"/api/v1/projects/{project_id}/integrations",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    providers = {item["provider"]: item for item in listing.json()["items"]}
    assert providers["github_actions"]["status"] == "connected"
    assert providers["gitlab"]["status"] == "coming_later"
    assert providers["gitlab"]["available"] is False

    updated = await auth_client.patch(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=headers,
        json={"auto_start_analysis": False, "workflow_filters": {"mode": "all", "names": []}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["auto_start_analysis"] is False

    tested = await auth_client.post(
        f"/api/v1/projects/{project_id}/integrations/github/test",
        headers=headers,
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["ok"] is True

    workflows = await auth_client.get(
        f"/api/v1/projects/{project_id}/integrations/github/workflows",
        headers=headers,
    )
    assert workflows.status_code == 200, workflows.text
    assert {item["name"] for item in workflows.json()["items"]} == {"CI", "Deploy"}

    disconnected = await auth_client.delete(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=headers,
    )
    assert disconnected.status_code == 200, disconnected.text

    after = await auth_client.get(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=headers,
    )
    assert after.status_code == 404


@pytest.mark.asyncio
async def test_status_and_installation_endpoints(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)

    status_response = await auth_client.get(
        "/api/v1/integrations/github/status",
        headers=headers,
    )
    assert status_response.status_code == 200, status_response.text
    payload = status_response.json()
    assert payload["enabled"] is True
    assert payload["webhook_configured"] is True
    assert payload["installation_count"] == 0
    # Secrets must never leak through the status endpoint.
    assert "secret" not in json.dumps(payload).lower().replace("webhook_configured", "")

    await _connect_repository(auth_client, headers, project_id)

    installations = await auth_client.get(
        "/api/v1/integrations/github/installations",
        headers=headers,
    )
    assert installations.status_code == 200, installations.text
    items = installations.json()["items"]
    assert len(items) == 1
    assert items[0]["github_installation_id"] == FAKE_INSTALLATION_ID

    repositories = await auth_client.get(
        f"/api/v1/integrations/github/installations/{items[0]['id']}/repositories",
        headers=headers,
    )
    assert repositories.status_code == 200, repositories.text
    repos = repositories.json()["items"]
    connected = [r for r in repos if r["github_repository_id"] == FAKE_REPOSITORY_ID]
    assert connected and connected[0]["connected_project_id"] == project_id


@pytest.mark.asyncio
async def test_setup_state_from_another_organization_is_rejected(
    auth_client: AsyncClient,
) -> None:
    headers_a, _ = await _register_owner(auth_client)
    project_a = await _create_project(auth_client, headers_a)
    install_url = await auth_client.post(
        "/api/v1/integrations/github/install-url",
        headers=headers_a,
        json={"project_id": project_a},
    )
    state = install_url.json()["state"]

    headers_b, _ = await _register_owner(auth_client)
    setup = await auth_client.post(
        "/api/v1/integrations/github/setup",
        headers=headers_b,
        json={"installation_id": FAKE_INSTALLATION_ID, "state": state},
    )
    assert setup.status_code == 400
    assert setup.json()["error_code"] == "INTEGRATION_STATE_MISMATCH"


@pytest.mark.asyncio
async def test_tampered_setup_state_is_rejected(auth_client: AsyncClient) -> None:
    headers, _ = await _register_owner(auth_client)
    setup = await auth_client.post(
        "/api/v1/integrations/github/setup",
        headers=headers,
        json={"installation_id": FAKE_INSTALLATION_ID, "state": "not-a-valid-state"},
    )
    assert setup.status_code == 400
    assert setup.json()["error_code"] == "INTEGRATION_STATE_INVALID"


@pytest.mark.asyncio
async def test_engineer_cannot_mutate_connection_but_can_read(auth_client: AsyncClient) -> None:
    headers, organization_id = await _register_owner(auth_client)
    project_id = await _create_project(auth_client, headers)
    await _connect_repository(auth_client, headers, project_id)

    engineer_email = f"eng-{uuid4().hex[:8]}@example.com"
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": engineer_email,
            "password": "StrongPassw0rd!",
            "full_name": "Engineer",
            "organization_name": "Throwaway Org",
        },
    )
    invite = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/members",
        headers=headers,
        json={"email": engineer_email, "role": "engineer"},
    )
    assert invite.status_code in (200, 201), invite.text

    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": engineer_email, "password": "StrongPassw0rd!"},
    )
    engineer_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}",
        "X-Organization-Id": organization_id,
    }

    readable = await auth_client.get(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=engineer_headers,
    )
    assert readable.status_code == 200, readable.text

    forbidden = await auth_client.delete(
        f"/api/v1/projects/{project_id}/integrations/github",
        headers=engineer_headers,
    )
    assert forbidden.status_code == 403
