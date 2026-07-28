"""Shared analysis context passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.ai.orchestration.models import (
    BudgetUsage,
    ConfidenceAssessment,
    EvidenceQualityAssessment,
    ExecutionBudget,
    ExecutionMode,
    FinalConfidenceAssessment,
    FusionResult,
    ProviderUsage,
    RetrievalQualityAssessment,
    RoutingDecision,
    UncertaintyAssessment,
    parse_execution_mode,
)
from app.domain.enums import FileType


@dataclass
class LoadedFile:
    file_id: UUID
    original_filename: str
    file_type: FileType
    content: str
    storage_path: str


@dataclass
class ClassificationCandidate:
    category_code: str
    confidence: float
    rank: int
    matched_rules: list[str] = field(default_factory=list)
    root_cause_summary: str = ""
    technical_explanation: str = ""
    impact_summary: str = ""


@dataclass
class EvidenceCandidate:
    evidence_type: str
    source_name: str | None
    uploaded_file_id: UUID | None
    line_start: int | None
    line_end: int | None
    raw_excerpt: str
    normalized_excerpt: str
    explanation: str
    importance_score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    category_code: str | None = None


@dataclass
class RecommendationStepCandidate:
    step_number: int
    step_type: str
    title: str
    action: str
    explanation: str | None = None
    expected_result: str | None = None
    risk_level: str | None = None
    difficulty: str | None = None
    command_template: str | None = None


@dataclass
class RecommendationCandidate:
    root_cause_summary: str
    explanation: str
    confidence_score: float
    steps: list[RecommendationStepCandidate] = field(default_factory=list)
    llm_model: str = "template"


@dataclass
class StageResult:
    name: str
    status: str  # completed | skipped | failed | running | timed_out
    duration_ms: int | None = None
    detail: str | None = None


@dataclass
class AnalysisContext:
    """Mutable working state for one analysis run execution."""

    analysis_run_id: UUID
    incident_id: UUID
    organization_id: UUID | None = None
    file_ids: list[UUID] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    files: list[LoadedFile] = field(default_factory=list)
    combined_text: str = ""
    input_type: str = "mixed"
    signals: dict[str, Any] = field(default_factory=dict)
    classifications: list[ClassificationCandidate] = field(default_factory=list)
    evidence: list[EvidenceCandidate] = field(default_factory=list)
    recommendation: RecommendationCandidate | None = None
    stages: list[StageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    model_name: str = "rules-hybrid"
    model_version: str = "1.0.0"
    partial: bool = False
    retrieval_query: str = ""
    retrieved_chunks: list[Any] = field(default_factory=list)
    retrieval_backend: str | None = None
    embedding_provider_name: str | None = None
    llm_root_cause: dict[str, Any] | None = None
    grounding_valid: bool = False
    reasoning_provider_name: str | None = None

    # Module 8 typed orchestration state
    requested_execution_mode: ExecutionMode = ExecutionMode.RAG_LLM
    execution_mode: str = ExecutionMode.RAG_LLM.value
    effective_execution_mode: str = ExecutionMode.RAG_LLM.value
    initial_routing_decision: RoutingDecision | None = None
    post_retrieval_routing_decision: RoutingDecision | None = None
    routing_decision: dict[str, Any] = field(default_factory=dict)
    confidence_assessment: ConfidenceAssessment | None = None
    evidence_quality_assessment: EvidenceQualityAssessment | None = None
    uncertainty_assessment: UncertaintyAssessment | None = None
    retrieval_quality_assessment: RetrievalQualityAssessment | None = None
    final_confidence_assessment: FinalConfidenceAssessment | None = None
    fusion_result: FusionResult | None = None
    budget: ExecutionBudget | None = None
    budget_usage: BudgetUsage | None = None
    provider_usage: list[ProviderUsage] = field(default_factory=list)
    confidence_metrics: dict[str, Any] = field(default_factory=dict)
    cost_metrics: dict[str, Any] = field(default_factory=dict)
    evaluation_metadata: dict[str, Any] = field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str | None = None
    risk_level: str = "medium"

    @property
    def enable_rag(self) -> bool:
        return bool(self.options.get("enable_rag", False))

    @property
    def enable_llm(self) -> bool:
        return bool(self.options.get("enable_llm", False))

    @property
    def top_k(self) -> int:
        try:
            return max(1, min(10, int(self.options.get("top_k_predictions", 3))))
        except (TypeError, ValueError):
            return 3

    @property
    def generate_recommendations(self) -> bool:
        return bool(self.options.get("generate_recommendations", True))

    @property
    def requested_mode(self) -> str:
        return parse_execution_mode(
            self.options.get("execution_mode"),
            default=self.requested_execution_mode,
        ).value
