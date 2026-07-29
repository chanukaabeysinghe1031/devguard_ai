"""Tests for analysis evidence / sources / recommendations read APIs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


async def _register_and_login(auth_client: AsyncClient, email: str) -> tuple[str, str]:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "Artifacts Tester",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


@pytest.mark.asyncio
async def test_analysis_artifact_endpoints_return_persisted_rows(
    auth_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("ANALYSIS_EXECUTION_MODE", "sync")
    monkeypatch.setenv("ENABLE_RAG", "true")
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.setenv("RAG_BACKEND", "memory")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    get_settings.cache_clear()

    token, org_id = await _register_and_login(
        auth_client, f"artifacts-{uuid4().hex[:8]}@example.com"
    )
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Artifacts", "key": "AR", "ci_provider": "github_actions"},
    )
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "AccessDenied demo",
            "source": "manual_upload",
            "severity": "high",
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
                    "aws-deny.log",
                    (
                        b"An error occurred (AccessDenied) when calling the AssumeRole "
                        b"operation: User is not authorized to perform: sts:AssumeRole\n"
                    ),
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
        json={
            "analysis_type": "full",
            "file_ids": [file_id],
            "options": {"enable_rag": True, "enable_llm": True},
        },
    )
    assert analysis.status_code == 202, analysis.text
    run_id = analysis.json()["analysis_run_id"]
    assert analysis.json()["status"] == "completed"

    detail = await auth_client.get(f"/api/v1/analyses/{run_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["classification"]["category"] == "aws_permission_failure"
    assert body["evidence_count"] >= 1
    assert "retrieved_document_count" in body
    assert "processing_time_ms" in body

    evidence = await auth_client.get(f"/api/v1/analyses/{run_id}/evidence", headers=headers)
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["total_items"] >= 1
    assert evidence.json()["items"][0]["excerpt"]

    sources = await auth_client.get(f"/api/v1/analyses/{run_id}/sources", headers=headers)
    assert sources.status_code == 200, sources.text
    assert isinstance(sources.json()["items"], list)
    assert len(sources.json()["items"]) >= 1

    recommendations = await auth_client.get(
        f"/api/v1/analyses/{run_id}/recommendations",
        headers=headers,
    )
    assert recommendations.status_code == 200, recommendations.text
    assert len(recommendations.json()["items"]) >= 1
