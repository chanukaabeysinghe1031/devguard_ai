"""Phase 6A.4 causal hypothesis debug API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CausalHypothesisRunResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    status: str
    deterministic_count: int = 0
    llm_count: int = 0
    invalid_reference_count: int = 0
    duplicate_removed_count: int = 0
    generator_version: str
    prompt_version: str | None = None
    duration_ms: int | None = None
    warnings: list[str] = Field(default_factory=list)
    truncation_notes: list[str] = Field(default_factory=list)
    created_at: datetime


class CausalHypothesisListItem(BaseModel):
    id: UUID
    hypothesis_key: str
    rank_placeholder: int
    category_code: str | None = None
    title: str
    causal_claim: str
    status: str
    generator_type: str
    template_id: str | None = None
    generation_prior_score: float
    generation_confidence: float
    path_validation_status: str
    affected_path: str | None = None
    supporting_evidence_count: int = 0
    contradicting_evidence_count: int = 0
    missing_evidence: list[str] = Field(default_factory=list)
    critic_decision: str | None = None


class CausalHypothesisListResponse(BaseModel):
    items: list[CausalHypothesisListItem]
    total_items: int


class CausalHypothesisDetailResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    hypothesis_key: str
    rank_placeholder: int
    category_code: str | None = None
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    title: str
    causal_claim: str
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None
    affected_artifact_id: str | None = None
    affected_artifact_type: str | None = None
    affected_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    generator_type: str
    generator_name: str
    generator_version: str
    prompt_version: str | None = None
    template_id: str | None = None
    generation_confidence: float
    generation_prior_score: float
    status: str
    path_validation_status: str
    path_validation_warnings: list[str] = Field(default_factory=list)
    causal_path_node_ids: list[str] = Field(default_factory=list)
    causal_path_edge_ids: list[str] = Field(default_factory=list)
    expected_observations: list[str] = Field(default_factory=list)
    falsifying_observations: list[str] = Field(default_factory=list)
    proposed_verification_steps: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime


class HypothesisEvidenceLinkItem(BaseModel):
    id: UUID
    evidence_type: str
    relation: str
    confidence: float
    explanation: str | None = None
    evidence_item_id: str | None = None
    graph_node_id: str | None = None
    graph_edge_id: str | None = None
    artifact_id: str | None = None
    source_path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    extraction_method: str


class HypothesisEvidenceListResponse(BaseModel):
    items: list[HypothesisEvidenceLinkItem]
    total_items: int


class HypothesisCausalPathResponse(BaseModel):
    hypothesis_id: UUID
    path_validation_status: str
    path_validation_warnings: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    root_cause_node_id: str | None = None
    observed_failure_node_id: str | None = None


class HypothesisCriticResponse(BaseModel):
    hypothesis_id: UUID
    decision: str
    recommended_status: str
    explanation: str | None = None
    contradictions: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    graph_conflicts: list[str] = Field(default_factory=list)
    temporal_conflicts: list[str] = Field(default_factory=list)
    specificity_warning: str | None = None
    critic_version: str
    created_at: datetime
