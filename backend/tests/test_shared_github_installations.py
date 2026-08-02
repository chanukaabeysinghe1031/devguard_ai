"""Shared GitHub App installation multi-tenant security matrix (ADR-005 extension).

A single GitHub App installation is a global identity that may be granted
access by, and used from, several DevGuard organizations. These tests verify
that organization access grants, repository connections, and webhook
fan-out outcomes are fully independent per organization, and that one
organization can never read or affect another organization's installation
access, connection, or incident data.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
):
    return await client.post(
        WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": _sign(body),
        },
    )


async def _register_owner(client: AsyncClient) -> tuple[dict[str, str], str]:
    email = f"gh-shared-{uuid4().hex[:8]}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPassw0rd!",
            "full_name": "GitHub Owner",
            "organization_name": f"Shared GitHub Org {uuid4().hex[:6]}",
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
            "name": "Shared Service",
            "key": f"SH{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
            "default_branch": "main",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _complete_setup(client: AsyncClient, headers: dict[str, str], project_id: str) -> dict:
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
    return setup.json()


async def _connect_repository(
    client: AsyncClient,
    headers: dict[str, str],
    project_id: str,
    installation_row_id: str,
    **overrides,
) -> dict:
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


async def _onboard_organization(client: AsyncClient) -> tuple[dict[str, str], str, str, dict]:
    """Register an org, create a project, and link the shared fake installation."""
    headers, organization_id = await _register_owner(client)
    project_id = await _create_project(client, headers)
    setup = await _complete_setup(client, headers, project_id)
    return headers, organization_id, project_id, setup


@pytest.mark.asyncio
async def test_two_organizations_can_complete_setup_for_same_installation(
    auth_client: AsyncClient,
) -> None:
    headers_a, _, _, setup_a = await _onboard_organization(auth_client)
    headers_b, _, _, setup_b = await _onboard_organization(auth_client)

    assert setup_a["installation"]["github_installation_id"] == FAKE_INSTALLATION_ID
    assert setup_b["installation"]["github_installation_id"] == FAKE_INSTALLATION_ID
    # Same global installation identity for both organizations.
    assert setup_a["installation"]["id"] == setup_b["installation"]["id"]

    status_a = await auth_client.get("/api/v1/integrations/github/status", headers=headers_a)
    status_b = await auth_client.get("/api/v1/integrations/github/status", headers=headers_b)
    assert status_a.json()["installation_count"] == 1
    assert status_b.json()["installation_count"] == 1

    installations_a = await auth_client.get(
        "/api/v1/integrations/github/installations", headers=headers_a
    )
    installations_b = await auth_client.get(
        "/api/v1/integrations/github/installations", headers=headers_b
    )
    assert len(installations_a.json()["items"]) == 1
    assert len(installations_b.json()["items"]) == 1


@pytest.mark.asyncio
async def test_same_repository_can_connect_in_two_organizations(auth_client: AsyncClient) -> None:
    headers_a, _, project_a, setup_a = await _onboard_organization(auth_client)
    connection_a = await _connect_repository(
        auth_client, headers_a, project_a, setup_a["installation"]["id"]
    )

    headers_b, _, project_b, setup_b = await _onboard_organization(auth_client)
    connection_b = await _connect_repository(
        auth_client, headers_b, project_b, setup_b["installation"]["id"]
    )

    assert connection_a["github_repository_id"] == connection_b["github_repository_id"]
    assert connection_a["id"] != connection_b["id"]
    assert connection_a["project_id"] != connection_b["project_id"]


@pytest.mark.asyncio
async def test_organization_without_access_cannot_load_shared_installation(
    auth_client: AsyncClient,
) -> None:
    _, _, _, setup_a = await _onboard_organization(auth_client)
    installation_row_id = setup_a["installation"]["id"]

    headers_b, _ = await _register_owner(auth_client)
    # Org B never linked this installation — it has no access grant at all.
    repos = await auth_client.get(
        f"/api/v1/integrations/github/installations/{installation_row_id}/repositories",
        headers=headers_b,
    )
    assert repos.status_code == 404

    sync = await auth_client.post(
        f"/api/v1/integrations/github/installations/{installation_row_id}/sync",
        headers=headers_b,
    )
    assert sync.status_code == 404

    unlink = await auth_client.delete(
        f"/api/v1/integrations/github/installations/{installation_row_id}/link",
        headers=headers_b,
    )
    assert unlink.status_code == 404

    installations_b = await auth_client.get(
        "/api/v1/integrations/github/installations", headers=headers_b
    )
    assert installations_b.json()["items"] == []


@pytest.mark.asyncio
async def test_webhook_fans_out_to_two_organizations_independently(
    auth_client: AsyncClient,
) -> None:
    headers_a, _, project_a, setup_a = await _onboard_organization(auth_client)
    await _connect_repository(auth_client, headers_a, project_a, setup_a["installation"]["id"])

    headers_b, _, project_b, setup_b = await _onboard_organization(auth_client)
    await _connect_repository(auth_client, headers_b, project_b, setup_b["installation"]["id"])

    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=9990001),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202, response.text
    assert response.json()["processing_status"] == "completed"

    incidents_a = await auth_client.get(
        "/api/v1/incidents", headers=headers_a, params={"project_id": project_a}
    )
    incidents_b = await auth_client.get(
        "/api/v1/incidents", headers=headers_b, params={"project_id": project_b}
    )
    items_a = incidents_a.json()["items"]
    items_b = incidents_b.json()["items"]
    assert len(items_a) == 1
    assert len(items_b) == 1
    assert items_a[0]["id"] != items_b[0]["id"]

    # Each organization's activity feed shows only its own connection's outcome.
    activity_a = await auth_client.get(
        f"/api/v1/projects/{project_a}/integrations/github/activity", headers=headers_a
    )
    activity_b = await auth_client.get(
        f"/api/v1/projects/{project_b}/integrations/github/activity", headers=headers_b
    )
    assert activity_a.status_code == 200, activity_a.text
    assert activity_b.status_code == 200, activity_b.text
    assert len(activity_a.json()["items"]) == 1
    assert len(activity_b.json()["items"]) == 1
    assert activity_a.json()["items"][0]["processing_status"] == "completed"
    assert activity_b.json()["items"][0]["processing_status"] == "completed"
    assert activity_a.json()["items"][0]["related_incident_id"] == items_a[0]["id"]
    assert activity_b.json()["items"][0]["related_incident_id"] == items_b[0]["id"]
    # Org A's activity must never reference org B's incident, and vice versa.
    assert activity_a.json()["items"][0]["related_incident_id"] != items_b[0]["id"]
    assert activity_b.json()["items"][0]["related_incident_id"] != items_a[0]["id"]


@pytest.mark.asyncio
async def test_replaying_delivery_does_not_duplicate_per_connection_outcome(
    auth_client: AsyncClient,
    repository_db_session: AsyncSession,
) -> None:
    headers_a, _, project_a, setup_a = await _onboard_organization(auth_client)
    await _connect_repository(auth_client, headers_a, project_a, setup_a["installation"]["id"])

    headers_b, _, project_b, setup_b = await _onboard_organization(auth_client)
    await _connect_repository(auth_client, headers_b, project_b, setup_b["installation"]["id"])

    delivery_id = f"delivery-{uuid4().hex[:12]}"
    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=9990002),
        delivery_id=delivery_id,
    )
    assert response.status_code == 202, response.text

    incidents_a_first = await auth_client.get(
        "/api/v1/incidents", headers=headers_a, params={"project_id": project_a}
    )
    incidents_b_first = await auth_client.get(
        "/api/v1/incidents", headers=headers_b, params={"project_id": project_b}
    )
    incident_id_a = incidents_a_first.json()["items"][0]["id"]
    incident_id_b = incidents_b_first.json()["items"][0]["id"]

    # Simulate a redelivery/replay of the *same* durable delivery row by
    # reprocessing it directly against the same session the API used.
    from app.application.services.github_ingestion_service import GitHubIngestionService
    from app.application.services.webhook_delivery_service import WebhookDeliveryService
    from app.core.config import get_settings
    from app.infrastructure.integrations.factory import get_github_provider
    from app.infrastructure.storage import build_file_storage

    settings = get_settings()
    delivery = await WebhookDeliveryService(repository_db_session).get_by_delivery_id(
        delivery_id=delivery_id
    )
    assert delivery is not None

    ingestion = GitHubIngestionService(
        session=repository_db_session,
        settings=settings,
        provider=get_github_provider(settings),
        storage=build_file_storage(settings),
    )
    await ingestion.process(delivery)
    await repository_db_session.commit()

    incidents_a_second = await auth_client.get(
        "/api/v1/incidents", headers=headers_a, params={"project_id": project_a}
    )
    incidents_b_second = await auth_client.get(
        "/api/v1/incidents", headers=headers_b, params={"project_id": project_b}
    )
    assert len(incidents_a_second.json()["items"]) == 1
    assert len(incidents_b_second.json()["items"]) == 1
    assert incidents_a_second.json()["items"][0]["id"] == incident_id_a
    assert incidents_b_second.json()["items"][0]["id"] == incident_id_b


@pytest.mark.asyncio
async def test_disconnecting_one_organizations_access_leaves_other_intact(
    auth_client: AsyncClient,
) -> None:
    headers_a, _, project_a, setup_a = await _onboard_organization(auth_client)
    installation_row_id = setup_a["installation"]["id"]
    await _connect_repository(auth_client, headers_a, project_a, installation_row_id)

    headers_b, _, project_b, setup_b = await _onboard_organization(auth_client)
    await _connect_repository(auth_client, headers_b, project_b, setup_b["installation"]["id"])

    unlink = await auth_client.delete(
        f"/api/v1/integrations/github/installations/{installation_row_id}/link",
        headers=headers_a,
    )
    assert unlink.status_code == 200, unlink.text

    # Org A no longer sees the installation or its own connection.
    installations_a = await auth_client.get(
        "/api/v1/integrations/github/installations", headers=headers_a
    )
    assert installations_a.json()["items"] == []
    connection_a = await auth_client.get(
        f"/api/v1/projects/{project_a}/integrations/github", headers=headers_a
    )
    assert connection_a.status_code == 404

    # Org B is completely unaffected: same installation, still connected.
    installations_b = await auth_client.get(
        "/api/v1/integrations/github/installations", headers=headers_b
    )
    assert len(installations_b.json()["items"]) == 1
    connection_b = await auth_client.get(
        f"/api/v1/projects/{project_b}/integrations/github", headers=headers_b
    )
    assert connection_b.status_code == 200, connection_b.text

    # A subsequent webhook only reaches org B now.
    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=9990003),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202, response.text

    incidents_a = await auth_client.get(
        "/api/v1/incidents", headers=headers_a, params={"project_id": project_a}
    )
    incidents_b = await auth_client.get(
        "/api/v1/incidents", headers=headers_b, params={"project_id": project_b}
    )
    assert incidents_a.status_code == 200
    assert incidents_a.json()["items"] == []
    assert incidents_b.status_code == 200
    assert len(incidents_b.json()["items"]) == 1


@pytest.mark.asyncio
async def test_single_organization_happy_path_is_unaffected_by_shared_support(
    auth_client: AsyncClient,
) -> None:
    """A lone organization using the installation sees no shared-access side effects."""
    headers, _, project_id, setup = await _onboard_organization(auth_client)
    assert setup["installation"]["organization_access_status"] == "active"
    await _connect_repository(auth_client, headers, project_id, setup["installation"]["id"])

    response = await _post_webhook(
        auth_client,
        _workflow_run_payload(run_id=9990004),
        delivery_id=f"delivery-{uuid4().hex[:12]}",
    )
    assert response.status_code == 202, response.text
    assert response.json()["processing_status"] == "completed"

    incidents = await auth_client.get(
        "/api/v1/incidents", headers=headers, params={"project_id": project_id}
    )
    assert len(incidents.json()["items"]) == 1

    status_response = await auth_client.get(
        "/api/v1/integrations/github/status", headers=headers
    )
    assert status_response.json()["installation_count"] == 1
    assert status_response.json()["connection_count"] == 1
