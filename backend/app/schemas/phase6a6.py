"""Phase 6A.6 Part 1 counterfactual remediation debug API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CounterfactualRemediationRunResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    project_id: UUID | None = None
    incident_id: UUID | None = None
    status: str
    selected_hypothesis_ids: list[str] = Field(default_factory=list)
    selected_hypothesis_count: int = 0
    candidate_count: int = 0
    safe_candidate_count: int = 0
    incomplete_candidate_count: int = 0
    rejected_candidate_count: int = 0
    duration_ms: int | None = None
    context_version: str
    constraint_version: str
    planner_version: str
    template_registry_version: str
    snapshot_version: str
    configuration_snapshot: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime
    disclaimer: str = (
        "Candidates are hypothesis-conditional and unverified. "
        "No patches applied; no verifiers executed in Part 1."
    )


class CounterfactualRemediationCandidateListItem(BaseModel):
    id: UUID
    candidate_key: str
    hypothesis_id: UUID | None = None
    title: str
    summary: str
    artifact_type: str | None = None
    status: str
    template_id: str | None = None
    change_types: list[str] = Field(default_factory=list)
    target_paths: list[str] = Field(default_factory=list)
    generator_type: str | None = None
    risk_level: str | None = None
    blast_radius: str | None = None
    priority_status: str | None = None
    priority_score: float | None = None
    risk_score: float | None = None
    changed_file_count: int = 0
    changed_line_count: int = 0
    validation_status: str | None = None
    constraint_status: str | None = None


class CounterfactualRemediationCandidateListResponse(BaseModel):
    items: list[CounterfactualRemediationCandidateListItem]
    total_items: int
    page: int
    page_size: int


class CounterfactualRemediationCandidateDetailResponse(BaseModel):
    id: UUID
    remediation_run_id: UUID
    analysis_run_id: UUID
    hypothesis_id: UUID | None = None
    candidate_key: str
    title: str
    summary: str
    artifact_type: str | None = None
    category_code: str | None = None
    affected_artifact_ids: list[str] = Field(default_factory=list)
    primary_artifact_id: str | None = None
    target_paths: list[str] = Field(default_factory=list)
    change_types: list[str] = Field(default_factory=list)
    expected_effects: list[Any] = Field(default_factory=list)
    expected_preserved_behaviors: list[Any] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    rollback_plan: dict[str, Any] = Field(default_factory=dict)
    risk_summary: list[Any] = Field(default_factory=list)
    blast_radius_summary: dict[str, Any] = Field(default_factory=dict)
    generator_type: str | None = None
    generator_name: str | None = None
    generator_version: str | None = None
    template_id: str | None = None
    template_version: str | None = None
    status: str
    patch_format: str | None = None
    patch_hash: str | None = None
    has_rendered_patch: bool = False
    changed_file_count: int = 0
    changed_line_count: int = 0
    risk_score: float | None = None
    risk_level: str | None = None
    blast_radius: str | None = None
    priority_score: float | None = None
    priority_status: str | None = None
    deduplication_fingerprint: str | None = None
    validation_status: str | None = None
    constraint_status: str | None = None
    prompt_version: str | None = None
    side_effects_json: list[Any] = Field(default_factory=list)
    quality_components_json: dict[str, Any] = Field(default_factory=dict)
    risk_components_json: dict[str, Any] = Field(default_factory=dict)
    generation_provenance: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "Candidate is hypothesis-conditional and unverified. "
        "Not applied; priority_score is not verification confidence."
    )


class CounterfactualChangeItem(BaseModel):
    id: UUID
    artifact_id: str | None = None
    artifact_type: str | None = None
    source_path: str | None = None
    change_type: str
    target_property: str | None = None
    original_fragment_hash: str | None = None
    proposed_fragment_hash: str | None = None
    has_normalized_diff: bool = False
    expected_effect: str | None = None
    rationale: str = ""
    change_order: int = 0
    content_hash_before: str | None = None
    content_hash_after_candidate: str | None = None


class CounterfactualChangeListResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    items: list[CounterfactualChangeItem]
    total_items: int


class CounterfactualPatchResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    patch_format: str | None = None
    patch_hash: str | None = None
    rendered_patch: str | None = None
    changed_file_count: int = 0
    changed_line_count: int = 0
    redaction_note: str = "Secret values are never returned; fragments may be redacted."


class CounterfactualRiskResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    risk_score: float | None = None
    risk_level: str | None = None
    risk_components_json: dict[str, Any] = Field(default_factory=dict)
    risk_summary: list[Any] = Field(default_factory=list)
    disclaimer: str = "Static heuristic risk only — not verification confidence."


class CounterfactualSideEffectsResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    side_effects_json: list[Any] = Field(default_factory=list)
    disclaimer: str = "Heuristic side-effect predictions only."


class CounterfactualRollbackResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    rollback_plan: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = "Structured rollback plan only — no shell commands; not executed."


class CounterfactualConstraintValidationResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    validation_status: str | None = None
    constraint_status: str | None = None
    disclaimer: str = "Structural validation only — verifier CLIs are not executed."


class CounterfactualPrioritisationResponse(BaseModel):
    analysis_run_id: UUID
    prioritisation: dict[str, Any] = Field(default_factory=dict)
    candidates: list[CounterfactualRemediationCandidateListItem] = Field(default_factory=list)
    disclaimer: str = (
        "Priority orders candidates for later verification. "
        "Not the fix; not verification confidence."
    )

class CounterfactualStateSnapshotResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    snapshot_kind: str
    snapshot: dict[str, Any] = Field(default_factory=dict)
    redaction_note: str = (
        "Sensitive fragments redacted; prefer hashes and paths over secret values."
    )


class RemediationConstraintItem(BaseModel):
    id: UUID
    constraint_key: str
    constraint_type: str
    severity: str
    source_type: str
    description: str
    source_path: str | None = None
    is_blocking: bool = False
    satisfaction_status: str
    machine_readable_rule: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


class RemediationConstraintListResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    items: list[RemediationConstraintItem]
    total_items: int


class RemediationPreconditionItem(BaseModel):
    id: UUID
    condition_type: str
    description: str
    status: str
    is_required: bool = True
    evidence_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class RemediationPreconditionListResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    items: list[RemediationPreconditionItem]
    total_items: int


class RemediationVerificationRequirementItem(BaseModel):
    id: UUID
    requirement_key: str
    verifier_type: str
    required: bool = True
    reason: str = ""
    expected_check: str | None = None
    expected_success_condition: str | None = None
    blocking_on_failure: bool = True
    limitations: list[str] = Field(default_factory=list)
    status_note: str = "NOT_RUN in Part 1 — reserved requirement only."


class RemediationVerificationRequirementListResponse(BaseModel):
    candidate_id: UUID
    analysis_run_id: UUID
    items: list[RemediationVerificationRequirementItem]
    total_items: int
