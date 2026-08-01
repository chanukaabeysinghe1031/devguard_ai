"""ORM models for Phase 6A.2 temporal localisation and evidence graph.

Table shapes match ``alembic/versions/012_phase6a2_temporal_graph.py``
exactly. Class names use a ``Row`` suffix to avoid colliding with the domain
dataclasses in ``app.domain.temporal`` and ``app.domain.evidence_graph``.
"""

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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class TemporalLocalisationResultRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "temporal_localisation_results"
    __table_args__ = (
        Index(
            "ix_temporal_localisation_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
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
    artifact_bundle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifact_bundles.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    primary_failure_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_failure_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    primary_failure_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordering_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    timestamp_quality: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    heuristic_version: Mapped[str] = mapped_column(String(40), nullable=False)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_information: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    downstream_symptom_event_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    upstream_context_event_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    events: Mapped[list[TemporalEventRow]] = relationship(
        back_populates="localisation",
        cascade="all, delete-orphan",
    )
    links: Mapped[list[TemporalEventLinkRow]] = relationship(
        back_populates="localisation",
        cascade="all, delete-orphan",
    )


class TemporalEventRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "temporal_events"
    __table_args__ = (
        UniqueConstraint(
            "localisation_id", "event_key", name="uq_temporal_events_localisation_key"
        ),
        Index("ix_temporal_events_analysis", "analysis_run_id"),
        Index("ix_temporal_events_org", "organization_id"),
        Index("ix_temporal_events_type", "event_type"),
        Index("ix_temporal_events_primary", "is_candidate_primary_failure"),
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
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    localisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("temporal_localisation_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    step_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    is_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_candidate_primary_failure: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    localisation: Mapped[TemporalLocalisationResultRow] = relationship(back_populates="events")


class TemporalEventLinkRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "temporal_event_links"
    __table_args__ = (
        UniqueConstraint(
            "localisation_id",
            "source_event_key",
            "target_event_key",
            "link_type",
            "rule_id",
            name="uq_temporal_event_links_stable",
        ),
        Index("ix_temporal_event_links_analysis", "analysis_run_id"),
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
    localisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("temporal_localisation_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    link_type: Mapped[str] = mapped_column(String(64), nullable=False)
    derivation: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    supporting_event_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    proven_causality: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    localisation: Mapped[TemporalLocalisationResultRow] = relationship(back_populates="links")


class EvidenceGraphRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evidence_graphs"
    __table_args__ = (
        Index(
            "ix_evidence_graphs_org_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
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
    artifact_bundle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifact_bundles.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    builder_version: Mapped[str] = mapped_column(String(40), nullable=False)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_link_diagnostics: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    nodes: Mapped[list[EvidenceGraphNodeRow]] = relationship(
        back_populates="graph",
        cascade="all, delete-orphan",
        foreign_keys="[EvidenceGraphNodeRow.graph_id]",
    )
    edges: Mapped[list[EvidenceGraphEdgeRow]] = relationship(
        back_populates="graph",
        cascade="all, delete-orphan",
        foreign_keys="[EvidenceGraphEdgeRow.graph_id]",
    )
    consistency_reports: Mapped[list[GraphConsistencyReportRow]] = relationship(
        back_populates="graph",
        cascade="all, delete-orphan",
    )


class EvidenceGraphNodeRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evidence_graph_nodes"
    __table_args__ = (
        UniqueConstraint("graph_id", "stable_key", name="uq_evidence_graph_nodes_stable"),
        Index("ix_evidence_graph_nodes_analysis", "analysis_run_id"),
        Index("ix_evidence_graph_nodes_org", "organization_id"),
        Index("ix_evidence_graph_nodes_type", "node_type"),
        Index("ix_evidence_graph_nodes_artifact", "artifact_id"),
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
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_graphs.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_artifacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    stable_key: Mapped[str] = mapped_column(String(500), nullable=False)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    parser_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    node_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    graph: Mapped[EvidenceGraphRow] = relationship(
        back_populates="nodes",
        foreign_keys=[graph_id],
    )


class EvidenceGraphEdgeRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evidence_graph_edges"
    __table_args__ = (
        UniqueConstraint("graph_id", "stable_key", name="uq_evidence_graph_edges_stable"),
        Index("ix_evidence_graph_edges_analysis", "analysis_run_id"),
        Index("ix_evidence_graph_edges_type", "edge_type"),
        Index("ix_evidence_graph_edges_source", "source_node_id"),
        Index("ix_evidence_graph_edges_target", "target_node_id"),
        Index("ix_evidence_graph_edges_derivation", "derivation_type"),
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
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_graphs.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_graph_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    stable_key: Mapped[str] = mapped_column(String(700), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False)
    derivation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    rule_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    graph: Mapped[EvidenceGraphRow] = relationship(
        back_populates="edges",
        foreign_keys=[graph_id],
    )
    source_node: Mapped[EvidenceGraphNodeRow] = relationship(foreign_keys=[source_node_id])
    target_node: Mapped[EvidenceGraphNodeRow] = relationship(foreign_keys=[target_node_id])


class GraphConsistencyReportRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "graph_consistency_reports"
    __table_args__ = (
        Index(
            "ix_graph_consistency_org_analysis",
            "organization_id",
            "analysis_run_id",
        ),
        Index("ix_graph_consistency_status", "status"),
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
    graph_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_graphs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_node_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consistency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    invalid_edge_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    orphan_nodes: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_expected_links: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    conflicting_links: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    rule_results: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    graph: Mapped[EvidenceGraphRow] = relationship(back_populates="consistency_reports")
