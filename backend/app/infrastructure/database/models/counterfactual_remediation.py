"""ORM models for Phase 6A.6 counterfactual remediation foundation persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class CounterfactualRemediationRunRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "counterfactual_remediation_runs"
    __table_args__ = (
        Index(
            "ix_cf_rem_runs_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
        Index("ix_cf_rem_runs_status", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_ranking_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    selected_hypothesis_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    selected_hypothesis_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safe_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    incomplete_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_version: Mapped[str] = mapped_column(String(64), nullable=False)
    constraint_version: Mapped[str] = mapped_column(String(64), nullable=False)
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    template_registry_version: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_version: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CounterfactualRemediationCandidateRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "counterfactual_remediation_candidates"
    __table_args__ = (
        UniqueConstraint(
            "remediation_run_id",
            "candidate_key",
            name="uq_cf_rem_candidate_run_key",
        ),
        Index("ix_cf_rem_cand_analysis", "organization_id", "analysis_run_id"),
        Index("ix_cf_rem_cand_hypothesis", "hypothesis_id"),
        Index("ix_cf_rem_cand_status", "status"),
        Index("ix_cf_rem_cand_artifact", "artifact_type"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_artifact_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    primary_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_paths: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    change_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    current_state_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    counterfactual_state_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    expected_effects: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    expected_preserved_behaviors: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    expected_failure_condition: Mapped[dict[str, Any] | list[Any] | str | None] = mapped_column(
        JSONB, nullable=True
    )
    assumptions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    rollback_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    risk_summary: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    blast_radius_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    generator_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CounterfactualChangeRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "counterfactual_changes"
    __table_args__ = (
        Index("ix_cf_changes_candidate", "candidate_id"),
        Index("ix_cf_changes_artifact", "artifact_type"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_property: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_fragment: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_effect: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_failure_condition_removed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    graph_node_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    graph_edge_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    assumptions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    change_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash_before: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_hash_after_candidate: Mapped[str | None] = mapped_column(String(128), nullable=True)


class RemediationConstraintRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_constraints"
    __table_args__ = (
        Index("ix_cf_constraints_analysis", "organization_id", "analysis_run_id"),
        Index("ix_cf_constraints_hypothesis", "hypothesis_id"),
        Index("ix_cf_constraints_candidate", "candidate_id"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    constraint_key: Mapped[str] = mapped_column(String(128), nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_graph_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_graph_edge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_evidence_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    machine_readable_rule: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    expected_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    prohibited_value: Mapped[Any] = mapped_column(JSONB, nullable=True)
    scope: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_satisfied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    satisfaction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class RemediationPreconditionRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_preconditions"
    __table_args__ = (
        Index("ix_cf_precond_analysis", "organization_id", "analysis_run_id"),
        Index("ix_cf_precond_hypothesis", "hypothesis_id"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypotheses.id", ondelete="SET NULL"),
        nullable=True,
    )
    condition_type: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_current_state: Mapped[Any] = mapped_column(JSONB, nullable=True)
    actual_current_state: Mapped[Any] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    artifact_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    graph_node_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class RemediationVerificationRequirementRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_verification_requirements"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "requirement_key",
            name="uq_cf_verif_req_candidate_key",
        ),
        Index("ix_cf_verif_req_candidate", "candidate_id"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    requirement_key: Mapped[str] = mapped_column(String(128), nullable=False)
    verifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    expected_check: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_success_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocking_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    input_artifacts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class RemediationRiskSignalRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_risk_signals"
    __table_args__ = (
        Index("ix_cf_risk_candidate", "candidate_id"),
        Index("ix_cf_risk_type", "risk_type"),
    )

    remediation_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    affected_artifact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    affected_resource: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    constraint_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
