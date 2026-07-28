"""Typed Module 8 orchestration models (state only; no routing formulas)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class ExecutionMode(StrEnum):
    RULES_ONLY = "rules_only"
    RULES_RAG = "rules_rag"
    LLM_ONLY = "llm_only"
    RAG_LLM = "rag_llm"
    CONFIDENCE_ROUTED = "confidence_routed"


class ExecutionRoute(StrEnum):
    DETERMINISTIC_ONLY = "deterministic_only"
    DETERMINISTIC_WITH_RAG = "deterministic_with_rag"
    LOCAL_REASONING = "local_reasoning"
    RAG_WITH_LOCAL_REASONING = "rag_with_local_reasoning"
    EXTERNAL_LLM_WITHOUT_RAG = "external_llm_without_rag"
    RAG_WITH_EXTERNAL_LLM = "rag_with_external_llm"
    SAFE_FALLBACK = "safe_fallback"


class ConfidenceBand(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class UncertaintyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CostEstimationStatus(StrEnum):
    CALCULATED = "calculated"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class StageStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass
class ConfidenceAssessment:
    raw_confidence: float
    calibrated_confidence: float
    confidence_band: ConfidenceBand
    calibration_method: str
    supporting_signal_count: int
    conflicting_signal_count: int
    category_margin: float | None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence_band"] = self.confidence_band.value
        return data


@dataclass
class EvidenceQualityAssessment:
    evidence_quality_score: float
    coverage_score: float
    traceability_score: float
    specificity_score: float
    consistency_score: float
    duplicate_ratio: float
    unique_file_count: int
    direct_signature_count: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UncertaintyAssessment:
    uncertainty_score: float
    uncertainty_level: UncertaintyLevel
    ambiguity_score: float
    input_completeness: float
    evidence_coverage: float
    conflicting_categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["uncertainty_level"] = self.uncertainty_level.value
        return data


@dataclass
class RetrievalQualityAssessment:
    retrieval_executed: bool
    retrieval_quality_score: float | None
    relevance_score: float | None
    coverage_score: float | None
    diversity_score: float | None
    duplicate_ratio: float | None
    category_support_score: float | None
    documents_considered: int
    documents_selected: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def not_executed(
        cls,
        reason: str = "Retrieval was not executed.",
    ) -> RetrievalQualityAssessment:
        return cls(
            retrieval_executed=False,
            retrieval_quality_score=None,
            relevance_score=None,
            coverage_score=None,
            diversity_score=None,
            duplicate_ratio=None,
            category_support_score=None,
            documents_considered=0,
            documents_selected=0,
            reasons=[reason],
        )


@dataclass
class ExecutionBudget:
    max_provider_calls: int | None = None
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_estimated_cost_usd: Decimal | None = None
    max_latency_ms: int | None = None
    max_retrieval_calls: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_provider_calls": self.max_provider_calls,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_estimated_cost_usd": (
                str(self.max_estimated_cost_usd)
                if self.max_estimated_cost_usd is not None
                else None
            ),
            "max_latency_ms": self.max_latency_ms,
            "max_retrieval_calls": self.max_retrieval_calls,
        }


@dataclass
class BudgetUsage:
    provider_calls_used: int = 0
    input_tokens_used: int = 0
    output_tokens_used: int = 0
    estimated_external_cost_usd: Decimal | None = None
    retrieval_calls_used: int = 0
    elapsed_ms: int = 0
    cost_estimation_status: CostEstimationStatus = CostEstimationStatus.UNAVAILABLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_calls_used": self.provider_calls_used,
            "input_tokens_used": self.input_tokens_used,
            "output_tokens_used": self.output_tokens_used,
            "estimated_external_cost_usd": (
                str(self.estimated_external_cost_usd)
                if self.estimated_external_cost_usd is not None
                else None
            ),
            "retrieval_calls_used": self.retrieval_calls_used,
            "elapsed_ms": self.elapsed_ms,
            "cost_estimation_status": self.cost_estimation_status.value,
        }


@dataclass
class RoutingDecision:
    decision_stage: str
    selected_route: ExecutionRoute
    decision_reasons: list[str]
    baseline_confidence: float
    calibrated_confidence: float
    uncertainty_score: float
    evidence_quality_score: float
    retrieval_quality_score: float | None
    expected_cost_usd: Decimal | None
    expected_latency_ms: int | None
    rag_required: bool
    llm_required: bool
    local_reasoning_allowed: bool
    external_reasoning_allowed: bool
    fallback_route: ExecutionRoute
    policy_name: str
    policy_version: str
    configuration_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_stage": self.decision_stage,
            "selected_route": self.selected_route.value,
            "decision_reasons": list(self.decision_reasons),
            "baseline_confidence": self.baseline_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "uncertainty_score": self.uncertainty_score,
            "evidence_quality_score": self.evidence_quality_score,
            "retrieval_quality_score": self.retrieval_quality_score,
            "expected_cost_usd": (
                str(self.expected_cost_usd) if self.expected_cost_usd is not None else None
            ),
            "expected_latency_ms": self.expected_latency_ms,
            "rag_required": self.rag_required,
            "llm_required": self.llm_required,
            "local_reasoning_allowed": self.local_reasoning_allowed,
            "external_reasoning_allowed": self.external_reasoning_allowed,
            "fallback_route": self.fallback_route.value,
            "policy_name": self.policy_name,
            "policy_version": self.policy_version,
            "configuration_hash": self.configuration_hash,
        }


@dataclass
class ProviderUsage:
    provider: str
    model: str | None
    operation: str
    request_count: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_external_cost_usd: Decimal | None
    cost_estimation_status: CostEstimationStatus
    latency_ms: int
    success: bool
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "operation": self.operation,
            "request_count": self.request_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_external_cost_usd": (
                str(self.estimated_external_cost_usd)
                if self.estimated_external_cost_usd is not None
                else None
            ),
            "cost_estimation_status": self.cost_estimation_status.value,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error_type": self.error_type,
        }


@dataclass
class FinalConfidenceAssessment:
    baseline_confidence: float
    reasoner_confidence: float | None
    final_confidence: float
    confidence_delta: float
    agreement_status: str
    grounding_coverage: float
    unsupported_claim_count: int
    contradiction_count: int
    recalibration_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FusionResult:
    baseline_category: str
    reasoner_category: str | None
    selected_category: str
    override_applied: bool
    override_reason: str | None
    supporting_evidence_ids: list[str] = field(default_factory=list)
    supporting_document_ids: list[str] = field(default_factory=list)
    alternative_categories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_execution_mode(
    value: str | None,
    *,
    default: ExecutionMode = ExecutionMode.RAG_LLM,
) -> ExecutionMode:
    if value is None:
        return default
    try:
        return ExecutionMode(str(value))
    except ValueError:
        return default


HIGH_RISK_CATEGORIES = frozenset(
    {
        "security_misconfiguration",
        "aws_permission_failure",
        "terraform_failure",
        "docker_failure",
        "deployment_failure",
        "network_failure",
    }
)
