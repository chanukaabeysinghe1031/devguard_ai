"""Module 8 confidence-aware / cost-aware orchestration tests."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.orchestration.adaptive_router import AdaptiveExecutionRouter
from app.ai.orchestration.analysis_context import (
    AnalysisContext,
    ClassificationCandidate,
    EvidenceCandidate,
    LoadedFile,
)
from app.ai.orchestration.analysis_orchestrator import AnalysisOrchestrator
from app.ai.orchestration.budget_manager import AIExecutionBudgetManager
from app.ai.orchestration.confidence_calibrator import RuleBasedConfidenceCalibrator
from app.ai.orchestration.evidence_quality import EvidenceQualityEvaluator
from app.ai.orchestration.models import (
    ExecutionBudget,
    ExecutionMode,
    ExecutionRoute,
    RetrievalQualityAssessment,
)
from app.ai.orchestration.policy import RoutingPolicyConfig
from app.ai.orchestration.retrieval_quality import RetrievalQualityEvaluator
from app.ai.orchestration.uncertainty import UncertaintyEstimator
from app.ai.rag.embedding_provider import HashingEmbeddingProvider
from app.ai.rag.retriever import KnowledgeRetriever
from app.ai.rag.vector_store import InMemoryVectorStore
from app.ai.reasoning.reasoning_provider import LocalGroundedReasoningProvider
from app.ai.reasoning.root_cause_analyzer import RootCauseAnalyzer
from app.domain.enums import FileType, RiskLevel
from app.domain.interfaces.ai_providers import EmbeddedChunk


def _policy(**kwargs) -> RoutingPolicyConfig:
    base = {
        "enable_rag": True,
        "enable_llm": True,
        "enable_local_reasoner": True,
        "enable_external_llm": False,
        "enable_confidence_routing": True,
    }
    base.update(kwargs)
    return RoutingPolicyConfig(**base)


def _build_context(*, options: dict, content: str | None = None) -> AnalysisContext:
    return AnalysisContext(
        analysis_run_id=uuid4(),
        incident_id=uuid4(),
        options=options,
        files=[
            LoadedFile(
                file_id=uuid4(),
                original_filename="deploy.log",
                file_type=FileType.LOG,
                content=content
                or (
                    "An error occurred (AccessDenied) when calling the UpdateService "
                    "operation: User is not authorized to perform: ecs:UpdateService\n"
                ),
                storage_path="x/deploy.log",
            )
        ],
    )


def _build_orchestrator(**policy_kwargs) -> AnalysisOrchestrator:
    store = InMemoryVectorStore()
    embeddings = HashingEmbeddingProvider()
    doc = (
        "AWS AccessDenied indicates missing IAM permissions. "
        "Grant least privilege and re-run deployment."
    )
    store.upsert(
        [
            EmbeddedChunk(
                chunk_id=str(uuid4()),
                text=doc,
                metadata={"provider": "aws", "document_status": "active"},
            )
        ],
        [embeddings.embed([doc])[0]],
    )
    retriever = KnowledgeRetriever(
        embedding_provider=embeddings,
        vector_store=store,
        retrieve_k=5,
        context_k=3,
    )
    analyzer = RootCauseAnalyzer(LocalGroundedReasoningProvider())
    policy = _policy(**policy_kwargs)
    return AnalysisOrchestrator(
        retriever=retriever,
        root_cause_analyzer=analyzer,
        policy=policy,
        router=AdaptiveExecutionRouter(policy),
    )


@pytest.mark.asyncio
async def test_rules_only_mode_skips_rag_and_llm() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "rules_only",
            "enable_rag": True,
            "enable_llm": True,
        }
    )
    result = await _build_orchestrator().run(ctx)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "skipped"
    assert stages["reasoning"] == "skipped"
    assert result.initial_routing_decision is not None
    assert result.initial_routing_decision.selected_route == ExecutionRoute.DETERMINISTIC_ONLY


@pytest.mark.asyncio
async def test_rules_rag_mode_runs_retrieval_only() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "rules_rag",
            "enable_rag": True,
            "enable_llm": True,
        }
    )
    result = await _build_orchestrator().run(ctx)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "completed"
    assert stages["reasoning"] == "skipped"
    assert result.retrieval_quality_assessment is not None
    assert result.retrieval_quality_assessment.retrieval_executed is True


@pytest.mark.asyncio
async def test_llm_only_skips_retrieval() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "llm_only",
            "enable_rag": True,
            "enable_llm": True,
        }
    )
    result = await _build_orchestrator().run(ctx)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "skipped"
    assert stages["reasoning"] == "completed"
    assert result.retrieval_quality_assessment is not None
    assert result.retrieval_quality_assessment.retrieval_executed is False
    assert result.retrieval_quality_assessment.retrieval_quality_score is None


@pytest.mark.asyncio
async def test_confidence_routed_high_confidence_deterministic() -> None:
    # Use a non-high-risk category so high_risk_requires_validation does not force RAG.
    ctx = _build_context(
        options={
            "execution_mode": "confidence_routed",
            "enable_rag": True,
            "enable_llm": True,
            "budget_usd": "1.00",
            "latency_limit_ms": 20000,
            "risk_level": "low",
        },
        content="npm ERR! ERESOLVE unable to resolve dependency tree\n",
    )
    result = await _build_orchestrator().run(ctx)
    assert result.initial_routing_decision is not None
    assert result.initial_routing_decision.selected_route == ExecutionRoute.DETERMINISTIC_ONLY
    assert result.confidence_assessment is not None
    assert result.confidence_assessment.calibrated_confidence >= 0.85
    assert result.classifications[0].category_code == "dependency_failure"


@pytest.mark.asyncio
async def test_high_risk_requires_validation_even_when_confident() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "confidence_routed",
            "enable_rag": True,
            "enable_llm": True,
            "risk_level": "high",
            "budget_usd": "1.00",
            "latency_limit_ms": 30000,
        }
    )
    result = await _build_orchestrator(high_risk_requires_validation=True).run(ctx)
    assert result.initial_routing_decision is not None
    assert result.initial_routing_decision.rag_required is True


def test_calibrator_is_deterministic_and_clamped() -> None:
    ctx = _build_context(options={})
    ctx.classifications = [
        ClassificationCandidate(
            category_code="aws_permission_failure",
            confidence=0.95,
            rank=1,
            matched_rules=["aws_access_denied"],
        )
    ]
    ctx.evidence = [
        EvidenceCandidate(
            evidence_type="log_line",
            source_name="deploy.log",
            uploaded_file_id=uuid4(),
            line_start=1,
            line_end=2,
            raw_excerpt="AccessDenied",
            normalized_excerpt="AccessDenied ecs:UpdateService",
            explanation="Matched rule 'aws_access_denied'.",
            importance_score=0.95,
            category_code="aws_permission_failure",
        )
    ]
    first = RuleBasedConfidenceCalibrator().calibrate(ctx)
    second = RuleBasedConfidenceCalibrator().calibrate(ctx)
    assert first.calibrated_confidence == second.calibrated_confidence
    assert 0.0 <= first.calibrated_confidence <= 1.0
    assert first.calibration_method == "rule_based_heuristic_v1"


def test_duplicate_evidence_does_not_inflate_quality() -> None:
    ctx = _build_context(options={})
    ctx.classifications = [
        ClassificationCandidate(
            category_code="aws_permission_failure",
            confidence=0.9,
            rank=1,
            matched_rules=["aws_access_denied"],
        )
    ]
    shared = "AccessDenied ecs:UpdateService"
    file_id = uuid4()
    ctx.evidence = [
        EvidenceCandidate(
            evidence_type="log_line",
            source_name="a.log",
            uploaded_file_id=file_id,
            line_start=1,
            line_end=1,
            raw_excerpt=shared,
            normalized_excerpt=shared,
            explanation="Matched rule",
            importance_score=0.9,
            category_code="aws_permission_failure",
        ),
        EvidenceCandidate(
            evidence_type="log_line",
            source_name="a.log",
            uploaded_file_id=file_id,
            line_start=1,
            line_end=1,
            raw_excerpt=shared,
            normalized_excerpt=shared,
            explanation="Matched rule",
            importance_score=0.9,
            category_code="aws_permission_failure",
        ),
    ]
    quality = EvidenceQualityEvaluator().evaluate(ctx)
    assert quality.duplicate_ratio > 0
    assert 0.0 <= quality.evidence_quality_score <= 1.0


def test_uncertainty_not_exact_inverse_of_confidence() -> None:
    ctx = _build_context(options={})
    ctx.classifications = [
        ClassificationCandidate(
            category_code="aws_permission_failure",
            confidence=0.9,
            rank=1,
            matched_rules=["aws_access_denied"],
        )
    ]
    conf = RuleBasedConfidenceCalibrator().calibrate(ctx)
    evid = EvidenceQualityEvaluator().evaluate(ctx)
    unc = UncertaintyEstimator().evaluate_baseline(ctx, confidence=conf, evidence_quality=evid)
    assert abs((1.0 - conf.calibrated_confidence) - unc.uncertainty_score) > 0.01
    assert 0.0 <= unc.uncertainty_score <= 1.0


def test_skipped_retrieval_has_null_scores() -> None:
    assessment = RetrievalQualityAssessment.not_executed()
    assert assessment.retrieval_executed is False
    assert assessment.retrieval_quality_score is None
    assert assessment.relevance_score is None


def test_empty_executed_retrieval_is_low_quality() -> None:
    ctx = _build_context(options={})
    ctx.retrieved_chunks = []
    quality = RetrievalQualityEvaluator().evaluate(ctx)
    assert quality.retrieval_executed is True
    assert quality.retrieval_quality_score is not None
    assert quality.retrieval_quality_score < 0.3


def test_budget_unknown_pricing_is_null_not_zero() -> None:
    manager = AIExecutionBudgetManager(
        ExecutionBudget(max_provider_calls=2, max_retrieval_calls=2),
        llm_input_cost_per_million=None,
        llm_output_cost_per_million=None,
        local_provider=False,
    )
    manager.record_reasoning(
        provider="openai",
        model="gpt-4o-mini",
        latency_ms=10,
        success=True,
        input_tokens=100,
        output_tokens=50,
    )
    assert manager.usage.estimated_external_cost_usd is None
    assert manager.usage.cost_estimation_status.value == "unavailable"


def test_local_provider_cost_is_zero_not_applicable() -> None:
    manager = AIExecutionBudgetManager(
        ExecutionBudget(max_provider_calls=2),
        local_provider=True,
    )
    manager.record_reasoning(
        provider="local-grounded",
        model="local",
        latency_ms=5,
        success=True,
    )
    assert manager.usage.estimated_external_cost_usd == Decimal("0")
    assert manager.usage.cost_estimation_status.value == "not_applicable"


def test_request_budget_cannot_exceed_server_maximum() -> None:
    policy = _policy(max_budget_usd=Decimal("0.10"))
    router = AdaptiveExecutionRouter(policy)
    conf = RuleBasedConfidenceCalibrator().calibrate(_build_context(options={}))
    evid = EvidenceQualityEvaluator().evaluate(_build_context(options={}))
    unc = UncertaintyEstimator().evaluate_baseline(
        _build_context(options={}), confidence=conf, evidence_quality=evid
    )
    budget = AIExecutionBudgetManager(
        ExecutionBudget(
            max_provider_calls=0,
            max_retrieval_calls=2,
            max_estimated_cost_usd=Decimal("0.10"),
            max_latency_ms=1000,
        ),
        local_provider=True,
    )
    decision = router.route_initial(
        requested_mode=ExecutionMode.CONFIDENCE_ROUTED,
        confidence=conf,
        evidence_quality=evid,
        uncertainty=unc,
        risk=RiskLevel.LOW,
        category_code="aws_permission_failure",
        budget_manager=budget,
        provider_available=True,
        elapsed_ms=0,
    )
    assert decision.llm_required is False


def test_policy_hash_is_stable() -> None:
    a = _policy().configuration_hash()
    b = _policy().configuration_hash()
    assert a == b
    assert len(a) == 16


def test_initial_routing_does_not_use_retrieval_scores() -> None:
    """Guard against pre-retrieval fake retrieval quality."""
    ctx = _build_context(
        options={
            "execution_mode": "confidence_routed",
            "enable_rag": True,
            "enable_llm": True,
            "risk_level": "low",
        }
    )
    # Intentionally leave retrieved_chunks empty before routing.
    assert ctx.retrieved_chunks == []
    conf = RuleBasedConfidenceCalibrator().calibrate(
        AnalysisContext(
            analysis_run_id=uuid4(),
            incident_id=uuid4(),
            classifications=[
                ClassificationCandidate(
                    category_code="aws_permission_failure",
                    confidence=0.95,
                    rank=1,
                    matched_rules=["aws_access_denied"],
                )
            ],
            evidence=[
                EvidenceCandidate(
                    evidence_type="log_line",
                    source_name="a.log",
                    uploaded_file_id=uuid4(),
                    line_start=1,
                    line_end=2,
                    raw_excerpt="AccessDenied",
                    normalized_excerpt="AccessDenied",
                    explanation="Matched rule",
                    importance_score=0.95,
                    category_code="aws_permission_failure",
                )
            ],
            files=ctx.files,
            signals={"line_count": 5},
        )
    )
    evid = EvidenceQualityEvaluator().evaluate(
        AnalysisContext(
            analysis_run_id=uuid4(),
            incident_id=uuid4(),
            classifications=ctx.classifications,
            evidence=[
                EvidenceCandidate(
                    evidence_type="log_line",
                    source_name="a.log",
                    uploaded_file_id=uuid4(),
                    line_start=1,
                    line_end=2,
                    raw_excerpt="AccessDenied",
                    normalized_excerpt="AccessDenied",
                    explanation="Matched rule",
                    importance_score=0.95,
                    category_code="aws_permission_failure",
                )
            ],
            files=ctx.files,
        )
    )
    unc = UncertaintyEstimator().evaluate_baseline(ctx, confidence=conf, evidence_quality=evid)
    decision = AdaptiveExecutionRouter(_policy()).route_initial(
        requested_mode=ExecutionMode.CONFIDENCE_ROUTED,
        confidence=conf,
        evidence_quality=evid,
        uncertainty=unc,
        risk=RiskLevel.LOW,
        category_code="aws_permission_failure",
        budget_manager=AIExecutionBudgetManager(ExecutionBudget(max_provider_calls=2)),
        provider_available=True,
        elapsed_ms=0,
    )
    assert decision.retrieval_quality_score is None
    assert decision.decision_stage == "initial"


@pytest.mark.asyncio
async def test_rag_llm_runs_retrieval_and_reasoning() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "rag_llm",
            "enable_rag": True,
            "enable_llm": True,
        }
    )
    result = await _build_orchestrator().run(ctx)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "completed"
    assert stages["reasoning"] == "completed"
    assert result.evaluation_metadata is not None
    assert result.evaluation_metadata.get("rag_used") is True


@pytest.mark.asyncio
async def test_disabled_server_rag_cannot_be_enabled_by_request() -> None:
    ctx = _build_context(
        options={
            "execution_mode": "rules_rag",
            "enable_rag": True,
            "enable_llm": True,
        }
    )
    result = await _build_orchestrator(enable_rag=False).run(ctx)
    stages = {s.name: s.status for s in result.stages}
    assert stages["retrieving_knowledge"] == "skipped"


def test_parse_execution_mode_rejects_invalid_to_default() -> None:
    from app.ai.orchestration.models import parse_execution_mode

    assert parse_execution_mode("not_a_mode") == ExecutionMode.RAG_LLM
    assert parse_execution_mode("rules_only") == ExecutionMode.RULES_ONLY


def test_fusion_keeps_deterministic_on_weak_disagreement() -> None:
    from app.ai.orchestration.fusion import DiagnosisFusionService
    from app.ai.orchestration.models import (
        ConfidenceAssessment,
        ConfidenceBand,
        EvidenceQualityAssessment,
    )

    ctx = _build_context(options={})
    ctx.classifications = [
        ClassificationCandidate(
            category_code="aws_permission_failure",
            confidence=0.9,
            rank=1,
            matched_rules=["aws_access_denied"],
        )
    ]
    ctx.llm_root_cause = {
        "root_cause": {
            "category": "dependency_failure",
            "confidence": 0.5,
        },
        "supporting_evidence_ids": ["evidence-1"],
    }
    ctx.grounding_valid = False
    fusion = DiagnosisFusionService().fuse(
        ctx,
        confidence=ConfidenceAssessment(
            raw_confidence=0.9,
            calibrated_confidence=0.9,
            confidence_band=ConfidenceBand.HIGH,
            calibration_method="rule_based_heuristic_v1",
            supporting_signal_count=2,
            conflicting_signal_count=0,
            category_margin=0.4,
            reasons=[],
        ),
        evidence_quality=EvidenceQualityAssessment(
            evidence_quality_score=0.8,
            coverage_score=0.8,
            traceability_score=0.8,
            specificity_score=0.8,
            consistency_score=0.8,
            duplicate_ratio=0.0,
            unique_file_count=1,
            direct_signature_count=1,
            reasons=[],
        ),
        retrieval_quality=RetrievalQualityAssessment.not_executed(),
        risk=RiskLevel.HIGH,
    )
    assert fusion.override_applied is False
    assert fusion.selected_category == "aws_permission_failure"
    assert "dependency_failure" in fusion.alternative_categories


def test_routing_metadata_has_no_secret_material() -> None:
    decision = AdaptiveExecutionRouter(_policy()).route_for_mode(
        ExecutionMode.RULES_ONLY,
        confidence=RuleBasedConfidenceCalibrator().calibrate(_build_context(options={})),
        evidence_quality=EvidenceQualityEvaluator().evaluate(_build_context(options={})),
        uncertainty=UncertaintyEstimator().evaluate_baseline(
            _build_context(options={}),
            confidence=RuleBasedConfidenceCalibrator().calibrate(_build_context(options={})),
            evidence_quality=EvidenceQualityEvaluator().evaluate(_build_context(options={})),
        ),
        risk=RiskLevel.LOW,
        stage="initial",
    )
    blob = str(decision.to_dict()).lower()
    assert "sk-" not in blob
    assert "password" not in blob
    assert "-----begin" not in blob
    assert "prompt" not in blob
