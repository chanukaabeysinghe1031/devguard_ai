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
    disclaimer: str = "Candidate skeleton only — not verified, not applied."


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
