"""Phase 6A.5 hypothesis-directed retrieval debug API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class HypothesisRetrievalRunResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    hypothesis_generation_run_id: UUID | None = None
    status: str
    execution_mode: str
    hypothesis_count_requested: int = 0
    hypothesis_count_processed: int = 0
    session_count_complete: int = 0
    session_count_partial: int = 0
    session_count_failed: int = 0
    total_query_count: int = 0
    total_result_count: int = 0
    total_unique_source_count: int = 0
    duration_ms: int | None = None
    embedding_model_version: str | None = None
    retrieval_pipeline_version: str
    error_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class HypothesisRetrievalSessionListItem(BaseModel):
    id: UUID
    hypothesis_id: UUID
    hypothesis_key: str
    status: str
    execution_mode: str
    category_code: str | None = None
    query_count: int = 0
    accepted_result_count: int = 0
    unique_source_count: int = 0
    duration_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)


class HypothesisRetrievalSessionListResponse(BaseModel):
    items: list[HypothesisRetrievalSessionListItem]
    total_items: int


class HypothesisRetrievalSessionDetailResponse(BaseModel):
    id: UUID
    retrieval_run_id: UUID
    analysis_run_id: UUID
    hypothesis_id: UUID
    hypothesis_key: str
    status: str
    execution_mode: str
    retrieval_context_version: str
    retrieval_plan_version: str
    hypothesis_prior_score_snapshot: float = 0.0
    category_code: str | None = None
    causal_claim_snapshot: str
    affected_artifact_id: str | None = None
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None
    query_count: int = 0
    raw_result_count: int = 0
    accepted_result_count: int = 0
    unique_source_count: int = 0
    cache_hit_count: int = 0
    source_types_attempted: list[str] = Field(default_factory=list)
    source_types_succeeded: list[str] = Field(default_factory=list)
    source_types_unavailable: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime


class HypothesisRetrievalContextResponse(BaseModel):
    session_id: UUID
    context_version: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class HypothesisRetrievalPlanResponse(BaseModel):
    session_id: UUID
    plan_version: str
    snapshot: dict[str, Any] = Field(default_factory=dict)


class HypothesisRetrievalQueryItem(BaseModel):
    id: UUID
    query_id: str
    query_type: str
    normalized_query: str
    source_types: list[str] = Field(default_factory=list)
    status: str
    adapters_attempted: list[str] = Field(default_factory=list)
    adapters_succeeded: list[str] = Field(default_factory=list)
    raw_result_count: int = 0
    accepted_result_count: int = 0
    cache_hit: bool = False
    duration_ms: int | None = None
    failure_type: str | None = None
    warnings: list[str] = Field(default_factory=list)
    error_summary: str | None = None


class HypothesisRetrievalQueryListResponse(BaseModel):
    items: list[HypothesisRetrievalQueryItem]
    total_items: int


class HypothesisRetrievedItemResponse(BaseModel):
    id: UUID
    primary_query_id: str
    source_type: str
    source_system: str
    source_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    artifact_id: str | None = None
    graph_node_id: str | None = None
    graph_edge_id: str | None = None
    temporal_event_id: str | None = None
    historical_incident_id: str | None = None
    title: str | None = None
    text_excerpt: str
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    retrieval_score: float = 0.0
    lexical_score: float | None = None
    vector_score: float | None = None
    historical_score: float | None = None
    adapter_name: str
    adapter_version: str
    relation_candidate: str
    rank_within_query: int = 0
    global_session_order: int = 0
    redaction_status: str
    associated_query_ids: list[str] = Field(default_factory=list)


class HypothesisRetrievedItemListResponse(BaseModel):
    items: list[HypothesisRetrievedItemResponse]
    total_items: int
    page: int
    page_size: int


class HypothesisRetrievalIntelligenceListResponse(BaseModel):
    session_id: UUID
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_items: int = 0
    source: str = "session.metrics"
