"""ORM models for Phase 6A.5 hypothesis-directed retrieval persistence."""

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


class HypothesisRetrievalRunRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_retrieval_runs"
    __table_args__ = (
        Index(
            "ix_hyp_ret_runs_analysis",
            "organization_id",
            "analysis_run_id",
            unique=True,
        ),
        Index("ix_hyp_ret_runs_status", "status"),
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
    hypothesis_generation_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("causal_hypothesis_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    hypothesis_count_requested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypothesis_count_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_count_complete: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_count_partial: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    session_count_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_unique_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    embedding_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieval_pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HypothesisRetrievalSessionRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_retrieval_sessions"
    __table_args__ = (
        UniqueConstraint(
            "retrieval_run_id",
            "hypothesis_id",
            name="uq_hyp_ret_session_run_hypothesis",
        ),
        Index("ix_hyp_ret_sessions_analysis", "organization_id", "analysis_run_id"),
        Index("ix_hyp_ret_sessions_status", "status"),
        Index("ix_hyp_ret_sessions_hypothesis", "hypothesis_id"),
    )

    retrieval_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hypothesis_retrieval_runs.id", ondelete="CASCADE"),
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
    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("causal_hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    hypothesis_key: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    retrieval_context_version: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_plan_version: Mapped[str] = mapped_column(String(64), nullable=False)
    hypothesis_prior_score_snapshot: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    category_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    causal_claim_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    affected_artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    root_cause_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_failure_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_types_attempted: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    source_types_succeeded: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    source_types_unavailable: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    errors: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class HypothesisRetrievalQueryExecutionRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_retrieval_query_executions"
    __table_args__ = (
        UniqueConstraint("session_id", "query_id", name="uq_hyp_ret_query_session_qid"),
        Index("ix_hyp_ret_queries_type", "query_type"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hypothesis_retrieval_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    query_id: Mapped[str] = mapped_column(String(64), nullable=False)
    query_type: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    source_types: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    adapters_attempted: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    adapters_succeeded: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    raw_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class HypothesisRetrievedItemRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_retrieved_items"
    __table_args__ = (
        Index("ix_hyp_ret_items_session", "session_id"),
        Index("ix_hyp_ret_items_source", "source_type"),
        Index("ix_hyp_ret_items_artifact", "artifact_id"),
        Index("ix_hyp_ret_items_doc", "document_id"),
        Index("ix_hyp_ret_items_graph", "graph_node_id"),
        Index("ix_hyp_ret_items_hist", "historical_incident_id"),
        Index("ix_hyp_ret_items_adapter", "adapter_name"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hypothesis_retrieval_sessions.id", ondelete="CASCADE"),
        nullable=False,
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
    primary_query_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_system: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    graph_node_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    graph_edge_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    temporal_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    historical_incident_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    text_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    repository: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_timestamp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    lexical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    vector_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    historical_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    graph_distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    adapter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_version: Mapped[str] = mapped_column(String(40), nullable=False)
    embedding_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    relation_candidate: Mapped[str] = mapped_column(String(40), nullable=False)
    rank_within_query: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    global_session_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    item_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    redaction_status: Mapped[str] = mapped_column(String(40), nullable=False)


class HypothesisRetrievedItemQueryRow(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "hypothesis_retrieved_item_queries"
    __table_args__ = (UniqueConstraint("item_id", "query_id", name="uq_hyp_ret_item_query"),)

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hypothesis_retrieved_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_execution_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hypothesis_retrieval_query_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_id: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
