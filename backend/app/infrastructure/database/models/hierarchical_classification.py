"""ORM models for Phase 6A.3 hierarchical classification.

Table shapes match ``alembic/versions/013_phase6a3_hier_class.py``.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class TaxonomyMappingRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "taxonomy_mappings"
    __table_args__ = (
        UniqueConstraint(
            "legacy_category_code",
            "mapping_version",
            name="uq_taxonomy_mappings_code_version",
        ),
        Index("ix_taxonomy_mappings_l1", "level_1_code"),
        Index("ix_taxonomy_mappings_l2", "level_2_code"),
        Index("ix_taxonomy_mappings_l3", "level_3_code"),
    )

    legacy_category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_1_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_1_label: Mapped[str] = mapped_column(String(128), nullable=False)
    level_2_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_2_label: Mapped[str] = mapped_column(String(128), nullable=False)
    level_3_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_3_label: Mapped[str] = mapped_column(String(128), nullable=False)
    mapping_version: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class HierarchicalClassificationResultRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hierarchical_classification_results"
    __table_args__ = (
        Index(
            "ix_hier_class_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
        Index("ix_hier_class_status", "classification_status"),
        Index("ix_hier_class_category", "final_legacy_category_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    final_legacy_category_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_1_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_2_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_3_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    classification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    final_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    mapping_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    rule_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    learned_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    llm_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    evaluation_export: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ClassificationCandidateRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "classification_candidates"
    __table_args__ = (
        UniqueConstraint(
            "hierarchical_result_id",
            "rank",
            name="uq_classification_candidates_result_rank",
        ),
        Index("ix_class_candidates_analysis", "organization_id", "analysis_run_id"),
        Index("ix_class_candidates_source", "source_classifier"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hierarchical_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hierarchical_classification_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_code: Mapped[str] = mapped_column(String(64), nullable=False)
    level_1_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_2_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    level_3_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    source_classifier: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    supporting_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    contradicting_evidence: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    matched_rules: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class OpenSetAssessmentRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "open_set_assessments"
    __table_args__ = (
        UniqueConstraint("hierarchical_result_id", name="uq_open_set_assessments_result"),
        Index("ix_open_set_status", "status"),
        Index("ix_open_set_analysis", "organization_id", "analysis_run_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hierarchical_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hierarchical_classification_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    unknown_score: Mapped[float] = mapped_column(Float, nullable=False)
    maximum_known_score: Mapped[float] = mapped_column(Float, nullable=False)
    top_two_margin: Mapped[float] = mapped_column(Float, nullable=False)
    rule_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    representation_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_coverage: Mapped[float] = mapped_column(Float, nullable=False)
    disagreement_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    threshold_version: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered_conditions: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClassificationDisagreementResultRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "classification_disagreement_results"
    __table_args__ = (
        UniqueConstraint("hierarchical_result_id", name="uq_class_disagreement_result"),
        Index("ix_class_disagreement_level", "agreement_level"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hierarchical_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hierarchical_classification_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    agreement_level: Mapped[str] = mapped_column(String(40), nullable=False)
    agreed_level_1: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agreed_level_2: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agreed_level_3: Mapped[str | None] = mapped_column(String(64), nullable=True)
    conflicting_candidates: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    conflict_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    classifier_conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_distance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommended_action: Mapped[str] = mapped_column(String(64), nullable=False)
    additional_evidence_needed: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    confidence_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClassificationConfidenceComponentRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "classification_confidence_components"
    __table_args__ = (
        UniqueConstraint(
            "hierarchical_result_id",
            "component_name",
            name="uq_class_confidence_component",
        ),
        Index("ix_class_confidence_analysis", "organization_id", "analysis_run_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    hierarchical_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hierarchical_classification_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_name: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_value: Mapped[float] = mapped_column(Float, nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    contribution: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
