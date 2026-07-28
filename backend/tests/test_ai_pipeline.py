"""Module 6 deterministic AI analysis pipeline tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.classification.hybrid_classifier import HybridClassifier
from app.ai.orchestration.analysis_context import AnalysisContext, LoadedFile
from app.ai.orchestration.analysis_orchestrator import AnalysisOrchestrator
from app.domain.enums import FileType
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.evidence_item import EvidenceItem
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.prediction import Prediction
from app.infrastructure.database.models.recommendation import Recommendation
from app.infrastructure.database.models.recommendation_step import RecommendationStep


async def _register_and_login(auth_client: AsyncClient, email: str) -> tuple[str, str]:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "AI Tester",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


async def _incident_with_log(
    auth_client: AsyncClient,
    headers: dict,
    *,
    filename: str,
    content: bytes,
) -> tuple[str, str]:
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={
            "name": "AI Proj",
            "key": f"A{uuid4().hex[:4].upper()}",
            "ci_provider": "github_actions",
        },
    )
    assert project.status_code == 201, project.text
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "Pipeline failure",
            "source": "manual_upload",
            "severity": "high",
        },
    )
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    upload = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/files",
        headers=headers,
        files=[("files", (filename, content, "text/plain"))],
    )
    assert upload.status_code == 201, upload.text
    return incident_id, upload.json()["files"][0]["id"]


def test_hybrid_classifier_aws_access_denied() -> None:
    context = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        combined_text=(
            "An error occurred (AccessDenied) when calling the PutObject operation: "
            "User is not authorized to perform: s3:PutObject"
        ),
    )
    results = HybridClassifier().classify(context)
    assert results
    assert results[0].category_code == "aws_permission_failure"
    assert results[0].confidence >= 0.9


@pytest.mark.asyncio
async def test_orchestrator_skips_rag_and_llm_when_disabled() -> None:
    context = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        options={"enable_rag": False, "enable_llm": False},
        files=[
            LoadedFile(
                file_id=uuid4(),
                original_filename="ci.log",
                file_type=FileType.LOG,
                content="npm ERR! ERESOLVE unable to resolve dependency tree\n",
                storage_path="x/ci.log",
            )
        ],
    )
    result = await AnalysisOrchestrator().run(context)
    stage_map = {s.name: s.status for s in result.stages}
    assert stage_map["retrieving_knowledge"] == "skipped"
    assert stage_map["reasoning"] == "skipped"
    assert stage_map["classifying"] == "completed"
    # Intentional feature-flag skips are complete deterministic runs, not soft-fails.
    assert result.partial is False
    assert result.classifications[0].category_code == "dependency_failure"
    assert result.recommendation is not None
    assert result.recommendation.steps


@pytest.mark.asyncio
async def test_analysis_pipeline_persists_aws_classification(
    auth_client,
    repository_db_session: AsyncSession,
) -> None:
    token, org_id = await _register_and_login(auth_client, f"ai-aws-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    log = (
        b"2024-01-01T12:00:00Z ERROR deploy\n"
        b"An error occurred (AccessDenied) when calling the AssumeRole operation:\n"
        b"User: arn:aws:iam::123:user/ci is not authorized to perform: sts:AssumeRole\n"
        b"password=should_be_masked_already_but_check\n"
    )
    incident_id, file_id = await _incident_with_log(
        auth_client, headers, filename="aws-deny.log", content=log
    )

    analysis = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={
            "analysis_type": "full",
            "file_ids": [file_id],
            "options": {"enable_rag": False, "enable_llm": False},
        },
    )
    assert analysis.status_code == 202, analysis.text
    body = analysis.json()
    assert body["status"] == "completed"
    run_id = body["analysis_run_id"]

    detail = await auth_client.get(f"/api/v1/analyses/{run_id}", headers=headers)
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["status"] == "completed"
    assert detail_body["classification"]["category"] == "aws_permission_failure"
    assert detail_body["evidence_count"] >= 1
    assert detail_body["recommendation_count"] == 1
    assert detail_body["root_cause"]["summary"]
    stages = (detail_body["output_summary"] or {}).get("stages") or []
    stage_names = {s["name"] for s in stages}
    assert "classifying" in stage_names
    assert "retrieving_knowledge" in stage_names
    skipped = [s for s in stages if s["name"] in {"retrieving_knowledge", "reasoning"}]
    assert all(s["status"] == "skipped" for s in skipped)

    status = await auth_client.get(f"/api/v1/analyses/{run_id}/status", headers=headers)
    assert status.json()["progress_percentage"] == 100

    run = await repository_db_session.get(
        AnalysisRun,
        run_id,
        options=[selectinload(AnalysisRun.predictions)],
    )
    assert run is not None
    assert run.status.value == "completed"

    predictions = list(
        (
            await repository_db_session.scalars(
                select(Prediction).where(Prediction.analysis_run_id == run.id)
            )
        ).all()
    )
    assert predictions
    assert predictions[0].predicted_label == "aws_permission_failure"

    evidence = list(
        (
            await repository_db_session.scalars(
                select(EvidenceItem).where(EvidenceItem.analysis_run_id == run.id)
            )
        ).all()
    )
    assert evidence
    secret = "should_be_masked_already_but_check"
    assert all(secret not in (e.normalized_excerpt or "") for e in evidence)

    recommendations = list(
        (
            await repository_db_session.scalars(
                select(Recommendation).where(Recommendation.analysis_run_id == run.id)
            )
        ).all()
    )
    assert len(recommendations) == 1
    steps = list(
        (
            await repository_db_session.scalars(
                select(RecommendationStep).where(
                    RecommendationStep.recommendation_id == recommendations[0].id
                )
            )
        ).all()
    )
    assert len(steps) >= 3

    events = list(
        (
            await repository_db_session.scalars(
                select(IncidentEvent).where(
                    IncidentEvent.incident_id == run.incident_id,
                    IncidentEvent.event_type == "analysis_completed",
                )
            )
        ).all()
    )
    assert events


@pytest.mark.asyncio
async def test_analysis_fails_without_files(auth_client) -> None:
    token, org_id = await _register_and_login(
        auth_client, f"ai-empty-{uuid4().hex[:8]}@example.com"
    )
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Empty", "key": "EM", "ci_provider": "github_actions"},
    )
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "No files",
            "source": "manual_upload",
            "severity": "low",
        },
    )
    incident_id = incident.json()["id"]
    analysis = await auth_client.post(
        f"/api/v1/incidents/{incident_id}/analyses",
        headers=headers,
        json={"analysis_type": "full", "file_ids": []},
    )
    assert analysis.status_code == 202, analysis.text
    assert analysis.json()["status"] == "failed"
    run_id = analysis.json()["analysis_run_id"]
    detail = await auth_client.get(f"/api/v1/analyses/{run_id}", headers=headers)
    assert detail.json()["error_code"] == "ANALYSIS_FAILED"
