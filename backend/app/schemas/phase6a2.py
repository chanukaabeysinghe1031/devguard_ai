"""Phase 6A.2 debug API schemas (temporal localisation + evidence graph)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TemporalLocalisationResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    status: str
    primary_failure_event_id: str | None = None
    primary_failure_type: str | None = None
    primary_failure_summary: str | None = None
    ordering_method: str | None = None
    timestamp_quality: str | None = None
    confidence: float | None = None
    heuristic_version: str
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    downstream_symptom_event_ids: list[str] = Field(default_factory=list)
    upstream_context_event_ids: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    created_at: datetime


class TemporalEventItem(BaseModel):
    id: UUID
    event_key: str
    event_type: str
    sequence_index: int
    event_timestamp: datetime | None = None
    job_name: str | None = None
    step_name: str | None = None
    message: str | None = None
    severity: str
    is_failure: bool
    is_candidate_primary_failure: bool
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    extraction_confidence: float | None = None


class TemporalEventListResponse(BaseModel):
    items: list[TemporalEventItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class EvidenceGraphSummaryResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    status: str
    builder_version: str
    node_count: int = 0
    edge_count: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    missing_link_diagnostics: list[str] = Field(default_factory=list)
    created_at: datetime


class EvidenceGraphNodeItem(BaseModel):
    id: UUID
    stable_key: str
    node_type: str
    label: str
    artifact_id: UUID | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    confidence: float | None = None
    extraction_method: str | None = None


class EvidenceGraphNodeListResponse(BaseModel):
    items: list[EvidenceGraphNodeItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class EvidenceGraphEdgeItem(BaseModel):
    id: UUID
    source_node_id: UUID
    target_node_id: UUID
    edge_type: str
    derivation_type: str
    confidence: float
    explanation: str | None = None
    rule_id: str | None = None
    rule_version: str | None = None


class EvidenceGraphEdgeListResponse(BaseModel):
    items: list[EvidenceGraphEdgeItem]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class GraphConsistencyResponse(BaseModel):
    id: UUID
    graph_id: UUID
    analysis_run_id: UUID
    status: str
    valid_node_count: int
    valid_edge_count: int
    consistency_score: float
    invalid_edge_ids: list[Any] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    orphan_nodes: list[Any] = Field(default_factory=list)
    missing_expected_links: list[str] = Field(default_factory=list)
    conflicting_links: list[Any] = Field(default_factory=list)
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
