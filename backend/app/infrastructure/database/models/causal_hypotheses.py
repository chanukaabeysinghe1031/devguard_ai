"""ORM models for Phase 6A.4 competing causal hypotheses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
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


class CausalHypothesisRunRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "causal_hypothesis_runs"
    __table_args__ = (
        Index(
            "ix_hyp_runs_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
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
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    deterministic_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_reference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    truncation_notes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CausalHypothesisRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "causal_hypotheses"
    __table_args__ = (
        UniqueConstraint(
            "hypothesis_run_id",
            "hypothesis_key",
            name="uq_causal_hypotheses_run_key",
        ),
        UniqueConstraint(
            "hypothesis_run_id", "rank_placeholder", name="uq_causal_hypotheses_run_rank"
        ),
        Index("ix_causal_hyp_analysis", "organization_id", "analysis_run_id"),
        Index("ix_causal_hyp_status", "status"),
        Index("ix_causal_hyp_category", "category_code"),
        Index("ix_causal_hyp_root_node", "root_cause_node_id"),
        Index("ix_causal_hyp_dedupe", "hypothesis_run_id", "dedupe_fingerprint"),
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
    hypothesis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypothesis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hypothesis_key: Mapped[str] = mapped_column(String(32), nullable=False)
    rank_placeholder: Mapped[int] = mapped_column(Integer, nullable=False)
    category_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_1_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_2_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_3_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    causal_claim: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_failure_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    affected_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    affected_artifact_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    affected_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generator_type: Mapped[str] = mapped_column(String(40), nullable=False)
    generator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generation_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    generation_prior_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    path_validation_status: Mapped[str] = mapped_column(String(40), nullable=False)
    path_validation_warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    causal_path_node_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    causal_path_edge_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    expected_observations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    falsifying_observations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    proposed_verification_steps: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    limitations: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    dedupe_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HypothesisEvidenceLinkRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_evidence_links"
    __table_args__ = (
        Index("ix_hyp_evidence_hyp", "hypothesis_id"),
        Index("ix_hyp_evidence_rel", "relation"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("causal_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    graph_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    graph_edge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relation: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False)


class HypothesisCriticResultRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_critic_results"
    __table_args__ = (UniqueConstraint("hypothesis_id", name="uq_hypothesis_critic_hypothesis"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("causal_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    recommended_status: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    contradictions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    unsupported_claims: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    graph_conflicts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    temporal_conflicts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    specificity_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    critic_version: Mapped[str] = mapped_column(String(40), nullable=False)
