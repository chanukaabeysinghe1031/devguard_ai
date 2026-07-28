"""Module 7 grounded RAG and LLM reasoning tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.orchestration.analysis_context import AnalysisContext, EvidenceCandidate, LoadedFile
from app.ai.orchestration.analysis_orchestrator import AnalysisOrchestrator
from app.ai.rag.embedding_provider import HashingEmbeddingProvider
from app.ai.rag.query_builder import build_retrieval_query
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.rag.vector_store import InMemoryVectorStore, get_shared_memory_store
from app.ai.reasoning.output_validator import (
    GroundingValidationError,
    validate_root_cause_output,
)
from app.ai.reasoning.reasoning_provider import LocalGroundedReasoningProvider
from app.ai.reasoning.root_cause_analyzer import RootCauseAnalyzer
from app.core.config import get_settings
from app.domain.enums import FileType
from app.domain.interfaces.ai_providers import EmbeddedChunk
from app.infrastructure.database.models.retrieved_document import RetrievedDocument


async def _register_and_login(auth_client: AsyncClient, email: str) -> tuple[str, str]:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePassword123!",
            "full_name": "RAG Tester",
        },
    )
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePassword123!"},
    )
    body = login.json()
    return body["access_token"], body["user"]["memberships"][0]["organization_id"]


def test_query_builder_includes_category_and_evidence() -> None:
    context = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        combined_text="AccessDenied ecs:UpdateService arn:aws:iam::123:role/ci",
    )
    from app.ai.orchestration.analysis_context import ClassificationCandidate

    context.classifications = [
        ClassificationCandidate(
            category_code="aws_permission_failure",
            confidence=0.9,
            rank=1,
            root_cause_summary="IAM denied the action.",
        )
    ]
    context.evidence = [
        EvidenceCandidate(
            evidence_type="log_line",
            source_name="deploy.log",
            uploaded_file_id=uuid4(),
            line_start=1,
            line_end=2,
            raw_excerpt="AccessDenied",
            normalized_excerpt="AccessDenied ecs:UpdateService",
            explanation="rule",
            importance_score=0.9,
        )
    ]
    query = build_retrieval_query(context)
    assert "aws permission failure" in query.lower()
    assert "AccessDenied" in query


def test_grounding_rejects_unknown_evidence_ids() -> None:
    context = AnalysisContext(analysis_run_id=uuid4(), incident_id=uuid4())
    context.evidence = [
        EvidenceCandidate(
            evidence_type="log_line",
            source_name="a.log",
            uploaded_file_id=None,
            line_start=1,
            line_end=1,
            raw_excerpt="x",
            normalized_excerpt="x",
            explanation="e",
            importance_score=0.5,
        )
    ]
    with pytest.raises(GroundingValidationError):
        validate_root_cause_output(
            {
                "summary": "test",
                "root_cause": {
                    "category": "aws_permission_failure",
                    "explanation": "because",
                    "confidence": 0.9,
                },
                "supporting_evidence_ids": ["evidence-99"],
                "documentation_chunk_ids": [],
            },
            context,
        )


@pytest.mark.asyncio
async def test_local_reasoning_requires_real_evidence_ids() -> None:
    provider = LocalGroundedReasoningProvider()
    from app.domain.interfaces.ai_providers import RootCauseRequest

    result = await provider.generate_root_cause(
        RootCauseRequest(
            classification_category="aws_permission_failure",
            classification_confidence=0.9,
            root_cause_summary="Denied",
            technical_explanation="IAM denied",
            evidence=[{"id": "evidence-1", "excerpt": "AccessDenied"}],
            retrieved_docs=[],
            signals={},
            safety_rules=[],
        )
    )
    assert result["supporting_evidence_ids"] == ["evidence-1"]


@pytest.mark.asyncio
async def test_orchestrator_rag_and_llm_stages_complete() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    chunk_id = uuid4()
    text = (
        "AWS IAM AccessDenied means the principal is not authorized for the action. "
        "Grant least-privilege permission and re-run the workflow."
    )
    vector = embeddings.embed([text])[0]
    store.upsert(
        [
            EmbeddedChunk(
                chunk_id=str(chunk_id),
                text=text,
                metadata={"document_status": "active", "provider": "aws"},
            )
        ],
        [vector],
    )
    retriever = KnowledgeRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        retrieve_k=5,
        context_k=3,
    )
    orchestrator = AnalysisOrchestrator(
        retriever=retriever,
        root_cause_analyzer=RootCauseAnalyzer(LocalGroundedReasoningProvider()),
    )
    context = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        options={"enable_rag": True, "enable_llm": True},
        files=[
            LoadedFile(
                file_id=uuid4(),
                original_filename="deploy.log",
                file_type=FileType.LOG,
                content=(
                    "An error occurred (AccessDenied) when calling the UpdateService "
                    "operation: User is not authorized to perform: ecs:UpdateService\n"
                ),
                storage_path="x/deploy.log",
            )
        ],
    )
    result = await orchestrator.run(context)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "completed"
    assert stages["reasoning"] == "completed"
    assert result.retrieved_chunks
    assert result.grounding_valid is True
    assert result.llm_root_cause is not None
    assert result.recommendation is not None
    assert result.recommendation.llm_model.startswith("local-grounded")


@pytest.mark.asyncio
async def test_rag_llm_pipeline_persists_retrieved_documents(
    auth_client,
    repository_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENABLE_RAG", "true")
    monkeypatch.setenv("ENABLE_LLM", "true")
    monkeypatch.setenv("RAG_BACKEND", "memory")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    get_settings.cache_clear()
    get_shared_memory_store()._items.clear()

    token, org_id = await _register_and_login(auth_client, f"rag-{uuid4().hex[:8]}@example.com")
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    project = await auth_client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "RAG", "key": "RG", "ci_provider": "github_actions"},
    )
    incident = await auth_client.post(
        "/api/v1/incidents",
        headers=headers,
        json={
            "project_id": project.json()["id"],
            "title": "IAM deny",
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
                    "aws.log",
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
    assert analysis.json()["status"] == "completed"
    run_id = analysis.json()["analysis_run_id"]

    detail = await auth_client.get(f"/api/v1/analyses/{run_id}", headers=headers)
    body = detail.json()
    assert body["status"] == "completed"
    assert body["classification"]["category"] == "aws_permission_failure"
    summary = body["output_summary"] or {}
    assert summary.get("retrieved_count", 0) >= 1
    assert summary.get("grounding_valid") is True
    assert summary.get("execution_mode") in {
        "rules_only",
        "rules_rag",
        "llm_only",
        "rag_llm",
        "confidence_routed",
    }
    assert isinstance(summary.get("routing_decision"), dict)
    assert isinstance(summary.get("confidence_metrics"), dict)
    assert isinstance(summary.get("cost_metrics"), dict)
    assert summary.get("retrieval_quality") is not None
    assert summary.get("evaluation_metadata") is not None
    stages = {s["name"]: s["status"] for s in summary.get("stages") or []}
    assert stages.get("retrieving_knowledge") == "completed"
    assert stages.get("reasoning") == "completed"

    retrieved = list(
        (
            await repository_db_session.scalars(
                select(RetrievedDocument).where(RetrievedDocument.analysis_run_id == run_id)
            )
        ).all()
    )
    assert retrieved
    assert any(row.used_in_reasoning for row in retrieved)

    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_llm_soft_fails_to_deterministic_path() -> None:
    class BoomAnalyzer(RootCauseAnalyzer):
        async def analyze(self, context: AnalysisContext):
            raise RuntimeError("provider down")

    orchestrator = AnalysisOrchestrator(
        root_cause_analyzer=BoomAnalyzer(LocalGroundedReasoningProvider()),
    )
    context = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        options={"enable_rag": False, "enable_llm": True},
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
    result = await orchestrator.run(context)
    stages = {s.name: s.status for s in result.stages}
    assert stages["reasoning"] == "failed"
    assert stages["classifying"] == "completed"
    assert result.classifications
    assert result.recommendation is not None
    assert result.partial is True
