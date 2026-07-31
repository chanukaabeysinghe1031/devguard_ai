"""ORM models for Phase 6A.1 artifact bundles and parse results."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)


class AnalysisArtifactBundle(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "analysis_artifact_bundles"
    __table_args__ = (
        Index("ix_analysis_artifact_bundles_org_incident", "organization_id", "incident_id"),
        Index("ix_analysis_artifact_bundles_analysis_run_id", "analysis_run_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    repository: Mapped[str | None] = mapped_column(String(300), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    available_artifacts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_artifacts: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    collection_errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    quality_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    redaction_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    bundle_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    artifacts: Mapped[list[AnalysisArtifact]] = relationship(
        back_populates="bundle",
        cascade="all, delete-orphan",
    )


class AnalysisArtifact(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "analysis_artifacts"
    __table_args__ = (
        Index("ix_analysis_artifacts_bundle_kind", "bundle_id", "artifact_kind"),
        Index("ix_analysis_artifacts_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifact_bundles.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    acquisition_status: Mapped[str] = mapped_column(String(40), nullable=False)
    redaction_status: Mapped[str] = mapped_column(String(40), nullable=False)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    artifact_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    bundle: Mapped[AnalysisArtifactBundle] = relationship(back_populates="artifacts")
    parse_results: Mapped[list[ArtifactParseResult]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class ArtifactParseResult(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "artifact_parse_results"
    __table_args__ = (
        Index("ix_artifact_parse_results_artifact_id", "artifact_id"),
        Index("ix_artifact_parse_results_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifacts.id", ondelete="CASCADE"),
        nullable=False,
    )
    parser_name: Mapped[str] = mapped_column(String(80), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    entities: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    relationships: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    diagnostics: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_candidates: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    extraction_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    artifact: Mapped[AnalysisArtifact] = relationship(back_populates="parse_results")
