"""ORM models for Phase 6A.6 Part 3 independent verifier persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
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


class RemediationVerificationRunRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_verification_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "analysis_run_id",
            "candidate_id",
            name="uq_rem_verif_run_org_analysis_candidate",
        ),
        Index("ix_rem_verif_runs_analysis", "organization_id", "analysis_run_id"),
        Index("ix_rem_verif_runs_status", "status"),
        Index("ix_rem_verif_runs_consensus", "consensus_status"),
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
    remediation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    consensus_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    consensus_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RemediationVerificationResultRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "remediation_verification_results"
    __table_args__ = (
        UniqueConstraint(
            "verification_run_id",
            "verifier_name",
            name="uq_rem_verif_result_run_name",
        ),
        Index("ix_rem_verif_results_run", "verification_run_id"),
        Index("ix_rem_verif_results_analysis", "organization_id", "analysis_run_id"),
        Index("ix_rem_verif_results_verifier", "verifier_name"),
    )

    verification_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("remediation_verification_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("counterfactual_remediation_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    verifier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    verifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    stdout_truncated: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr_truncated: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts_checked: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    tool_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    returncode: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
