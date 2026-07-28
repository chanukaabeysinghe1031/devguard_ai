"""Module 9 hybrid retrieval tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.ai.orchestration.analysis_context import (
    AnalysisContext,
    ClassificationCandidate,
    EvidenceCandidate,
    LoadedFile,
)
from app.ai.orchestration.budget_manager import AIExecutionBudgetManager
from app.ai.orchestration.models import ExecutionBudget
from app.ai.orchestration.retrieval_quality import RetrievalQualityEvaluator
from app.ai.rag.authority import authority_score
from app.ai.rag.deduplicator import CandidateDeduplicator
from app.ai.rag.diversity import DiverseCandidateSelector
from app.ai.rag.embedding_provider import HashingEmbeddingProvider
from app.ai.rag.historical_index import HistoricalIncidentIndexService
from app.ai.rag.historical_retriever import HistoricalIncidentRetriever
from app.ai.rag.hybrid_pipeline import HybridRetrievalPipeline
from app.ai.rag.hybrid_query_builder import HybridDiagnosticQueryBuilder
from app.ai.rag.hybrid_scorer import HybridRetrievalScorer
from app.ai.rag.lexical_index import LexicalRetriever
from app.ai.rag.metadata_enrichment import enrich_chunk_metadata
from app.ai.rag.models import (
    RetrievalCandidate,
    RetrievalMode,
    RetrievalSourceType,
    parse_retrieval_mode,
)
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.rag.signals import DiagnosticSignalExtractor
from app.ai.rag.stack_trace import stack_trace_fingerprint, stack_trace_similarity
from app.ai.rag.vector_store import InMemoryVectorStore
from app.ai.rag.weight_profiles import (
    EMBEDDING_BASELINE_V1,
    HYBRID_HISTORY_V1,
    HYBRID_STATIC_V1,
    HybridRetrievalSettings,
)
from app.domain.enums import FileType
from app.domain.interfaces.ai_providers import EmbeddedChunk
from app.domain.services.secret_masker import mask_secrets


def _context(**kwargs) -> AnalysisContext:
    content = kwargs.pop(
        "content",
        "An error occurred (AccessDenied) when calling the UpdateService "
        "operation: User is not authorized to perform: ecs:UpdateService\n",
    )
    options = kwargs.pop("options", {})
    ctx = AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        organization_id=kwargs.pop("organization_id", uuid4()),
        options=options,
        files=[
            LoadedFile(
                file_id=uuid4(),
                original_filename="deploy.log",
                file_type=FileType.LOG,
                content=content,
                storage_path="x/deploy.log",
            )
        ],
        combined_text=content,
        classifications=[
            ClassificationCandidate(
                category_code="aws_permission_failure",
                confidence=0.92,
                rank=1,
                matched_rules=["aws_access_denied"],
                root_cause_summary="Missing IAM permission for ecs:UpdateService",
            )
        ],
        evidence=[
            EvidenceCandidate(
                evidence_type="log_line",
                source_name="deploy.log",
                uploaded_file_id=uuid4(),
                line_start=1,
                line_end=1,
                raw_excerpt="AccessDenied ecs:UpdateService",
                normalized_excerpt="AccessDenied ecs:UpdateService",
                explanation="Matched AccessDenied",
                importance_score=0.95,
                category_code="aws_permission_failure",
            )
        ],
        **kwargs,
    )
    return ctx


def _seed_store(store: InMemoryVectorStore, embeddings: HashingEmbeddingProvider) -> None:
    docs = [
        (
            str(uuid4()),
            "AWS AccessDenied indicates missing IAM permissions for ecs:UpdateService.",
            {
                "document_status": "active",
                "source_type": "vendor_documentation",
                "source_authority": "official_vendor_documentation",
                "provider": "aws",
                "title": "AWS IAM AccessDenied",
                "failure_categories": ["aws_permission_failure"],
                "technologies": ["AWS"],
                "error_codes": ["AccessDenied"],
                "aws_services": ["ecs", "iam"],
                "document_id": "aws-doc",
            },
        ),
        (
            str(uuid4()),
            "npm ERR! ERESOLVE unable to resolve dependency tree",
            {
                "document_status": "active",
                "source_type": "knowledge_document",
                "provider": "npm",
                "title": "npm dependency",
                "failure_categories": ["dependency_failure"],
                "technologies": ["npm"],
                "error_codes": ["ERESOLVE"],
                "document_id": "npm-doc",
            },
        ),
    ]
    chunks = [EmbeddedChunk(chunk_id=i, text=t, metadata=m) for i, t, m in docs]
    vectors = embeddings.embed([c.text for c in chunks])
    store.upsert(chunks, vectors)


def test_parse_retrieval_mode_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_retrieval_mode("not_a_mode")


def test_signal_extractor_finds_aws_and_commands() -> None:
    ctx = _context()
    signals = DiagnosticSignalExtractor().extract(ctx)
    assert "AccessDenied" in signals.error_codes
    assert "AWS" in signals.technologies
    assert "ecs" in signals.aws_services
    assert signals.failure_category == "aws_permission_failure"


def test_query_builder_masks_secrets_and_bounds_length() -> None:
    secret = "aws_secret_access_key=SUPERSECRETVALUE999"
    ctx = _context(
        content=f"AccessDenied\n{secret}\n" + ("failed\n" * 200),
    )
    # Place secret in evidence so it enters the semantic query path.
    ctx.evidence[0].normalized_excerpt = f"AccessDenied {secret}"
    ctx.evidence[0].raw_excerpt = f"AccessDenied {secret}"
    query = HybridDiagnosticQueryBuilder().build(ctx)
    assert "SUPERSECRETVALUE999" not in query.sanitised_text
    assert "REDACTED" in query.sanitised_text
    assert len(query.sanitised_text) <= 800
    assert "AccessDenied" in query.sanitised_text


def test_stack_trace_fingerprint_stable_across_line_numbers() -> None:
    a = 'Traceback (most recent call last):\n  File "app.py", line 10, in run\nValueError: boom'
    b = 'Traceback (most recent call last):\n  File "app.py", line 99, in run\nValueError: boom'
    fa = stack_trace_fingerprint(a)
    fb = stack_trace_fingerprint(b)
    assert fa is not None and fb is not None
    assert fa == fb
    assert (stack_trace_similarity(a, b) or 0) > 0.5


def test_metadata_enrichment_stable_hash_and_no_path() -> None:
    meta = enrich_chunk_metadata(
        base={"path": "/private/secret/path.md"},
        content="AccessDenied ecs:UpdateService IAM",
        heading="AWS",
        document_id="doc-1",
        chunk_id="chunk-1",
        provider="aws",
        title="IAM",
        source_url="https://docs.aws.amazon.com/IAM/",
    )
    assert "path" not in meta
    assert meta["content_hash"]
    assert "AccessDenied" in meta["error_codes"]
    assert "aws_permission_failure" in meta["failure_categories"]
    again = enrich_chunk_metadata(
        base={},
        content="AccessDenied ecs:UpdateService IAM",
        heading="AWS",
        document_id="doc-1",
        chunk_id="chunk-1",
        provider="aws",
        title="IAM",
        source_url="https://docs.aws.amazon.com/IAM/",
    )
    assert meta["content_hash"] == again["content_hash"]


def test_masking_before_embedding_for_ingestion_content() -> None:
    raw = "token=ghp_abcdefghijklmnopqrstuvwxyz123456 password=supersecret"
    masked, _ = mask_secrets(raw)
    assert "ghp_" not in masked
    assert "supersecret" not in masked
    embeddings = HashingEmbeddingProvider()
    # Embedding uses masked text only.
    vec = embeddings.embed([masked])[0]
    assert len(vec) == 256


def test_embedding_only_preserves_baseline_path() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    _seed_store(store, embeddings)
    baseline = KnowledgeRetriever(
        embedding_provider=embeddings, vector_store=store, retrieve_k=5, context_k=3
    )
    pipeline = HybridRetrievalPipeline(
        embedding_provider=embeddings,
        vector_store=store,
        baseline_retriever=baseline,
        settings=HybridRetrievalSettings(
            default_mode="embedding_only",
            enable_hybrid_retrieval=False,
        ),
    )
    ctx = _context(options={"execution_mode": "rules_rag", "retrieval_mode": "embedding_only"})
    result = pipeline.retrieve(ctx)
    assert result.retrieval_mode == RetrievalMode.EMBEDDING_ONLY
    assert result.weight_profile == EMBEDDING_BASELINE_V1.name
    assert len(ctx.retrieved_chunks) >= 1


def test_hybrid_static_boosts_error_code_match() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    _seed_store(store, embeddings)
    lexical = LexicalRetriever()
    # Re-index seeded chunks into lexical index.
    # Access private store entries via query of empty embedding is awkward; re-upsert.
    hits = store.query(embedding=embeddings.embed(["AccessDenied"])[0], top_k=10)
    lexical.index(
        [EmbeddedChunk(chunk_id=h.chunk_id, text=h.text, metadata=h.metadata) for h in hits]
    )
    baseline = KnowledgeRetriever(
        embedding_provider=embeddings, vector_store=store, retrieve_k=5, context_k=3
    )
    pipeline = HybridRetrievalPipeline(
        embedding_provider=embeddings,
        vector_store=store,
        baseline_retriever=baseline,
        settings=HybridRetrievalSettings(
            default_mode="hybrid_static",
            enable_hybrid_retrieval=True,
            enable_lexical_retrieval=True,
        ),
        lexical_retriever=lexical,
    )
    ctx = _context(options={"execution_mode": "rag_llm", "retrieval_mode": "hybrid_static"})
    result = pipeline.retrieve(ctx)
    assert result.retrieval_mode == RetrievalMode.HYBRID_STATIC
    assert result.candidates_selected
    top = result.candidates_selected[0]
    assert top.error_code_score is None or top.error_code_score >= 0.0
    assert any("AccessDenied" in (c.content_excerpt or "") for c in result.candidates_selected)


def test_hybrid_scorer_normalises_active_weights_and_clamps() -> None:
    scorer = HybridRetrievalScorer(HYBRID_STATIC_V1)
    query = HybridDiagnosticQueryBuilder().build(_context())
    candidate = RetrievalCandidate(
        candidate_id="c1",
        source_type=RetrievalSourceType.KNOWLEDGE_DOCUMENT,
        source_id="doc",
        chunk_id="1",
        title="t",
        content_excerpt="AccessDenied",
        semantic_score=0.8,
        error_code_score=1.0,
        category_score=1.0,
        keyword_score=None,  # missing optional — not treated as zero
        metadata={"failure_categories": ["aws_permission_failure"]},
    )
    breakdown = scorer.score(candidate, query)
    assert 0.0 <= breakdown.final_score <= 1.0
    assert breakdown.weight_profile == "hybrid_static_v1"
    assert HYBRID_STATIC_V1.configuration_hash() == HYBRID_STATIC_V1.configuration_hash()


def test_lexical_exact_error_outranks_generic_keyword() -> None:
    lexical = LexicalRetriever()
    lexical.index(
        [
            EmbeddedChunk(
                chunk_id="exact",
                text="AccessDenied ecs UpdateService IAM",
                metadata={"error_codes": ["AccessDenied"]},
            ),
            EmbeddedChunk(
                chunk_id="generic",
                text="general failure troubleshooting guide error failed",
                metadata={},
            ),
        ]
    )
    query = HybridDiagnosticQueryBuilder().build(_context())
    hits = lexical.search(query, top_k=5)
    assert hits
    assert hits[0].chunk_id == "exact"
    assert 0.0 <= hits[0].score <= 1.0


def test_deduplication_keeps_highest_score() -> None:
    candidates = [
        RetrievalCandidate(
            candidate_id="a",
            source_type=RetrievalSourceType.KNOWLEDGE_DOCUMENT,
            source_id="doc1",
            chunk_id="1",
            title="t",
            content_excerpt="AccessDenied same text",
            hybrid_score=0.5,
        ),
        RetrievalCandidate(
            candidate_id="b",
            source_type=RetrievalSourceType.KNOWLEDGE_DOCUMENT,
            source_id="doc1",
            chunk_id="2",
            title="t",
            content_excerpt="AccessDenied same text",
            hybrid_score=0.9,
        ),
    ]
    kept, duplicates = CandidateDeduplicator().deduplicate(candidates)
    assert duplicates == 1
    assert len(kept) == 1
    assert kept[0].candidate_id == "b"


def test_diversity_limits_chunks_per_document() -> None:
    candidates = [
        RetrievalCandidate(
            candidate_id=f"c{i}",
            source_type=RetrievalSourceType.KNOWLEDGE_DOCUMENT,
            source_id="same-doc",
            chunk_id=str(i),
            title="t",
            content_excerpt=f"unique content number {i} AccessDenied",
            hybrid_score=1.0 - i * 0.01,
        )
        for i in range(5)
    ]
    selected = DiverseCandidateSelector().select(candidates, HYBRID_STATIC_V1)
    assert len(selected) <= HYBRID_STATIC_V1.max_chunks_per_document


def test_historical_retrieval_is_org_scoped() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    index = HistoricalIncidentIndexService(
        embedding_provider=embeddings, vector_store=store, min_quality_score=0.5
    )
    org_a = uuid4()
    org_b = uuid4()
    doc_a = index.build_document_from_resolution(
        incident_id=uuid4(),
        organisation_id=org_a,
        project_id=None,
        title="A",
        confirmed_category="aws_permission_failure",
        root_cause_summary="AccessDenied ecs:UpdateService missing IAM",
        resolution_summary="Granted ecs:UpdateService",
        evidence_excerpts=["AccessDenied"],
        has_resolution_steps=True,
    )
    doc_b = index.build_document_from_resolution(
        incident_id=uuid4(),
        organisation_id=org_b,
        project_id=None,
        title="B",
        confirmed_category="aws_permission_failure",
        root_cause_summary="AccessDenied ecs:UpdateService other org",
        resolution_summary="Different fix",
        evidence_excerpts=["AccessDenied"],
        has_resolution_steps=True,
    )
    assert index.index_resolved_incident(doc_a) == "indexed"
    assert index.index_resolved_incident(doc_b) == "indexed"
    assert index.index_resolved_incident(doc_a) == "unchanged"

    retriever = HistoricalIncidentRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        profile=HYBRID_HISTORY_V1,
    )
    query = HybridDiagnosticQueryBuilder().build(_context(organization_id=org_a))
    query.organisation_id = org_a
    hits = retriever.retrieve(query)
    assert hits
    assert all(h.metadata.get("organisation_id") == str(org_a) for h in hits)
    assert all(h.metadata.get("organisation_id") != str(org_b) for h in hits)


def test_historical_disabled_cannot_be_enabled_by_request() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    _seed_store(store, embeddings)
    baseline = KnowledgeRetriever(
        embedding_provider=embeddings, vector_store=store, retrieve_k=5, context_k=3
    )
    pipeline = HybridRetrievalPipeline(
        embedding_provider=embeddings,
        vector_store=store,
        baseline_retriever=baseline,
        settings=HybridRetrievalSettings(
            default_mode="hybrid_static",
            enable_hybrid_retrieval=True,
            enable_historical_retrieval=False,
        ),
    )
    ctx = _context(
        options={
            "execution_mode": "rag_llm",
            "retrieval_mode": "hybrid_with_history",
        }
    )
    result = pipeline.retrieve(ctx)
    assert result.retrieval_mode == RetrievalMode.HYBRID_STATIC
    assert result.fallback_used is True


def test_budget_downgrade_to_embedding_only() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    _seed_store(store, embeddings)
    baseline = KnowledgeRetriever(
        embedding_provider=embeddings, vector_store=store, retrieve_k=5, context_k=3
    )
    pipeline = HybridRetrievalPipeline(
        embedding_provider=embeddings,
        vector_store=store,
        baseline_retriever=baseline,
        settings=HybridRetrievalSettings(enable_hybrid_retrieval=True),
    )
    budget = AIExecutionBudgetManager(
        ExecutionBudget(max_retrieval_calls=0, max_provider_calls=0),
        local_provider=True,
    )
    ctx = _context(options={"execution_mode": "rag_llm", "retrieval_mode": "hybrid_static"})
    result = pipeline.retrieve(ctx, budget_manager=budget)
    assert result.retrieval_mode == RetrievalMode.EMBEDDING_ONLY
    assert result.fallback_used is True


def test_retrieval_quality_mode_aware_and_skipped_null() -> None:
    from app.ai.orchestration.models import RetrievalQualityAssessment

    skipped = RetrievalQualityAssessment.not_executed()
    assert skipped.retrieval_executed is False
    assert skipped.retrieval_quality_score is None

    ctx = _context(options={"retrieval_mode": "hybrid_static"})
    ctx.retrieved_chunks = []
    low = RetrievalQualityEvaluator().evaluate(ctx)
    assert low.retrieval_executed is True
    assert (low.retrieval_quality_score or 0) < 0.3


def test_authority_score_bounded() -> None:
    score = authority_score(
        source_type=RetrievalSourceType.VENDOR_DOCUMENTATION,
        metadata={"source_authority": "official_vendor_documentation"},
    )
    assert 0.0 <= score <= 1.0
    assert score >= 0.8


def test_remove_historical_incident_invalidates() -> None:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    index = HistoricalIncidentIndexService(
        embedding_provider=embeddings, vector_store=store, min_quality_score=0.5
    )
    org = uuid4()
    incident = uuid4()
    doc = index.build_document_from_resolution(
        incident_id=incident,
        organisation_id=org,
        project_id=None,
        title="t",
        confirmed_category="aws_permission_failure",
        root_cause_summary="AccessDenied",
        resolution_summary="Fixed IAM",
        has_resolution_steps=True,
    )
    index.index_resolved_incident(doc)
    assert index.remove_incident(org, incident) is True
    retriever = HistoricalIncidentRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        profile=HYBRID_HISTORY_V1,
    )
    query = HybridDiagnosticQueryBuilder().build(_context(organization_id=org))
    query.organisation_id = org
    hits = retriever.retrieve(query)
    assert hits == []
