"""Analysis API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ExecutionModeLiteral = Literal[
    "rules_only",
    "rules_rag",
    "llm_only",
    "rag_llm",
    "confidence_routed",
]

RetrievalModeLiteral = Literal[
    "embedding_only",
    "hybrid_static",
    "hybrid_with_history",
    "keyword_only",
]


class AnalysisOptions(BaseModel):
    enable_rag: bool = False
    enable_llm: bool = False
    generate_recommendations: bool = True
    top_k_predictions: int = Field(default=3, ge=1, le=10)
    execution_mode: ExecutionModeLiteral = "rag_llm"
    retrieval_mode: RetrievalModeLiteral | None = None
    budget_usd: Decimal | None = Field(default=None, ge=0)
    latency_limit_ms: int = Field(default=30000, ge=1000, le=300000)
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"

    @field_validator("budget_usd", mode="before")
    @classmethod
    def empty_budget_to_none(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return value


class StartAnalysisRequest(BaseModel):
    analysis_type: str = Field(default="full", max_length=40)
    file_ids: list[UUID] = Field(default_factory=list)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ReanalyseRequest(BaseModel):
    reason: str = Field(min_length=1)
    file_ids: list[UUID] = Field(default_factory=list)


class AnalysisAcceptedResponse(BaseModel):
    analysis_run_id: UUID
    incident_id: UUID
    status: str
    progress_percentage: int = 0
    created_at: datetime


class AnalysisStageResponse(BaseModel):
    name: str
    status: str
    duration_ms: int | None = None


class AnalysisStatusResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    current_stage: str | None = None
    progress_percentage: int
    started_at: datetime | None = None
    estimated_remaining_seconds: int | None = None
    stages: list[AnalysisStageResponse] = Field(default_factory=list)


class AnalysisRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    status: str
    analysis_type: str
    progress_percentage: int
    created_at: datetime | None = None
    completed_at: datetime | None = None


class AnalysisOrchestrationSummary(BaseModel):
    """Safe Module 8/9 orchestration summary for API consumers."""

    requested_execution_mode: str | None = None
    effective_execution_mode: str | None = None
    selected_route: str | None = None
    confidence: float | None = None
    confidence_band: str | None = None
    uncertainty_score: float | None = None
    uncertainty_level: str | None = None
    evidence_quality_score: float | None = None
    retrieval_used: bool = False
    reasoning_used: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    routing_policy_version: str | None = None
    provider_usage_summary: list[dict[str, Any]] = Field(default_factory=list)
    cost_summary: dict[str, Any] | None = None
    latency_summary: dict[str, Any] | None = None
    retrieval_mode: str | None = None
    candidates_considered: int | None = None
    results_selected: int | None = None
    duplicate_count: int | None = None
    historical_results_used: int | None = None
    retrieval_quality_score: float | None = None
    retrieval_configuration_hash: str | None = None
    retrieval_fallback_used: bool = False
    retrieval_fallback_reason: str | None = None


class AnalysisRunDetailResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    analysis_type: str
    duration_ms: int | None = None
    progress_percentage: int
    current_stage: str | None = None
    input_summary: dict[str, Any] | None = None
    output_summary: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
    classification: dict[str, Any] | None = None
    root_cause: dict[str, Any] | None = None
    evidence_count: int = 0
    recommendation_count: int = 0
    model_versions: dict[str, Any] | None = None
    orchestration: AnalysisOrchestrationSummary | None = None
