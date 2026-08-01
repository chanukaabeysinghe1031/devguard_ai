# ruff: noqa: E501
"""Migration 015 — Phase 6A.5 hypothesis-directed retrieval persistence.

Additive only. No historical backfill. Feature flags default off for the
experimental path. Does not imply causal ranking.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "015_phase6a5_hyp_retrieval"
down_revision: str | None = "014_phase6a4_hypotheses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hypothesis_retrieval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_generation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=40), nullable=False),
        sa.Column("hypothesis_count_requested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hypothesis_count_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("session_count_complete", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("session_count_partial", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("session_count_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_unique_source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("embedding_model_version", sa.String(length=128), nullable=True),
        sa.Column("retrieval_pipeline_version", sa.String(length=64), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hypothesis_generation_run_id"],
            ["causal_hypothesis_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hyp_ret_runs_analysis",
        "hypothesis_retrieval_runs",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )
    op.create_index("ix_hyp_ret_runs_status", "hypothesis_retrieval_runs", ["status"])

    op.create_table(
        "hypothesis_retrieval_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("retrieval_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_key", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("execution_mode", sa.String(length=40), nullable=False),
        sa.Column("retrieval_context_version", sa.String(length=64), nullable=False),
        sa.Column("retrieval_plan_version", sa.String(length=64), nullable=False),
        sa.Column(
            "hypothesis_prior_score_snapshot", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("category_code", sa.String(length=64), nullable=True),
        sa.Column("causal_claim_snapshot", sa.Text(), nullable=False),
        sa.Column("affected_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("root_cause_node_id", sa.String(length=128), nullable=True),
        sa.Column("observed_failure_node_id", sa.String(length=128), nullable=True),
        sa.Column("query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source_types_attempted", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "source_types_succeeded", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "source_types_unavailable", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("plan_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["retrieval_run_id"], ["hypothesis_retrieval_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "retrieval_run_id",
            "hypothesis_id",
            name="uq_hyp_ret_session_run_hypothesis",
        ),
    )
    op.create_index(
        "ix_hyp_ret_sessions_analysis",
        "hypothesis_retrieval_sessions",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index("ix_hyp_ret_sessions_status", "hypothesis_retrieval_sessions", ["status"])
    op.create_index(
        "ix_hyp_ret_sessions_hypothesis", "hypothesis_retrieval_sessions", ["hypothesis_id"]
    )

    op.create_table(
        "hypothesis_retrieval_query_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_id", sa.String(length=64), nullable=False),
        sa.Column("query_type", sa.String(length=64), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=False),
        sa.Column("source_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("adapters_attempted", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("adapters_succeeded", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("failure_type", sa.String(length=64), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["hypothesis_retrieval_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "query_id", name="uq_hyp_ret_query_session_qid"),
    )
    op.create_index(
        "ix_hyp_ret_queries_type",
        "hypothesis_retrieval_query_executions",
        ["query_type"],
    )

    op.create_table(
        "hypothesis_retrieved_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_query_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("document_id", sa.String(length=255), nullable=True),
        sa.Column("chunk_id", sa.String(length=255), nullable=True),
        sa.Column("artifact_id", sa.String(length=128), nullable=True),
        sa.Column("graph_node_id", sa.String(length=128), nullable=True),
        sa.Column("graph_edge_id", sa.String(length=128), nullable=True),
        sa.Column("temporal_event_id", sa.String(length=128), nullable=True),
        sa.Column("historical_incident_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("text_excerpt", sa.Text(), nullable=False),
        sa.Column("normalized_text_hash", sa.String(length=64), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("repository", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("source_timestamp", sa.String(length=64), nullable=True),
        sa.Column("retrieval_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("lexical_score", sa.Float(), nullable=True),
        sa.Column("vector_score", sa.Float(), nullable=True),
        sa.Column("historical_score", sa.Float(), nullable=True),
        sa.Column("graph_distance", sa.Float(), nullable=True),
        sa.Column("adapter_name", sa.String(length=64), nullable=False),
        sa.Column("adapter_version", sa.String(length=40), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=128), nullable=True),
        sa.Column("relation_candidate", sa.String(length=40), nullable=False),
        sa.Column("rank_within_query", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("global_session_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("redaction_status", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["hypothesis_retrieval_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hyp_ret_items_session", "hypothesis_retrieved_items", ["session_id"])
    op.create_index("ix_hyp_ret_items_source", "hypothesis_retrieved_items", ["source_type"])
    op.create_index("ix_hyp_ret_items_artifact", "hypothesis_retrieved_items", ["artifact_id"])
    op.create_index("ix_hyp_ret_items_doc", "hypothesis_retrieved_items", ["document_id"])
    op.create_index("ix_hyp_ret_items_graph", "hypothesis_retrieved_items", ["graph_node_id"])
    op.create_index(
        "ix_hyp_ret_items_hist",
        "hypothesis_retrieved_items",
        ["historical_incident_id"],
    )
    op.create_index("ix_hyp_ret_items_adapter", "hypothesis_retrieved_items", ["adapter_name"])

    op.create_table(
        "hypothesis_retrieved_item_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_execution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("query_id", sa.String(length=64), nullable=False),
        sa.Column("adapter_name", sa.String(length=64), nullable=True),
        sa.Column("retrieval_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["hypothesis_retrieved_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["query_execution_id"],
            ["hypothesis_retrieval_query_executions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", "query_id", name="uq_hyp_ret_item_query"),
    )


def downgrade() -> None:
    op.drop_table("hypothesis_retrieved_item_queries")
    op.drop_table("hypothesis_retrieved_items")
    op.drop_table("hypothesis_retrieval_query_executions")
    op.drop_table("hypothesis_retrieval_sessions")
    op.drop_table("hypothesis_retrieval_runs")
