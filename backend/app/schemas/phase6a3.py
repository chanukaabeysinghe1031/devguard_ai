"""Phase 6A.3 debug API schemas (hierarchical classification + open-set)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaxonomyPathItem(BaseModel):
    legacy_category_code: str
    level_1_code: str
    level_1_label: str
    level_2_code: str
    level_2_label: str
    level_3_code: str
    level_3_label: str
    mapping_version: str
    is_active: bool = True
    notes: str = ""


class FailureTaxonomyResponse(BaseModel):
    mapping_version: str
    paths: list[TaxonomyPathItem]
    aliases: dict[str, str] = Field(default_factory=dict)
    frozen_codes: list[str] = Field(default_factory=list)


class HierarchicalClassificationResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    final_legacy_category_code: str | None = None
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    classification_status: str
    final_confidence: float | None = None
    mapping_version: str
    model_versions: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    rule_result: dict[str, Any] | None = None
    learned_result: dict[str, Any] | None = None
    llm_result: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int | None = None
    created_at: datetime


class ClassificationCandidateItem(BaseModel):
    id: UUID
    category_code: str
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    score: float
    source_classifier: str
    rank: int
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)


class ClassificationCandidateListResponse(BaseModel):
    items: list[ClassificationCandidateItem]
    total_items: int


class OpenSetAssessmentResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    status: str
    unknown_score: float
    maximum_known_score: float
    top_two_margin: float
    rule_coverage: float
    representation_distance: float | None = None
    evidence_coverage: float
    disagreement_level: str | None = None
    threshold_version: str
    triggered_conditions: list[str] = Field(default_factory=list)
    explanation: str | None = None
    created_at: datetime


class ClassificationDisagreementResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    agreement_level: str
    agreed_level_1: str | None = None
    agreed_level_2: str | None = None
    agreed_level_3: str | None = None
    conflicting_candidates: list[str] = Field(default_factory=list)
    conflict_type: str
    evidence_conflict: bool
    classifier_conflict: bool
    category_distance: float
    recommended_action: str
    additional_evidence_needed: list[str] = Field(default_factory=list)
    confidence_penalty: float
    explanation: str | None = None
    created_at: datetime


class ClassificationConfidenceComponentItem(BaseModel):
    component_name: str
    raw_value: float
    normalized_value: float
    weight: float
    contribution: float
    source: str
    explanation: str | None = None


class ClassificationConfidenceResponse(BaseModel):
    analysis_run_id: UUID
    final_confidence: float | None = None
    components: list[ClassificationConfidenceComponentItem]
