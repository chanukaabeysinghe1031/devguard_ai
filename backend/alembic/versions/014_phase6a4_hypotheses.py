# ruff: noqa: E501
"""Migration 014 — Phase 6A.4 competing causal hypotheses.

Additive only. No historical backfill. Feature flags default off.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "014_phase6a4_hypotheses"
down_revision: str | None = "013_phase6a3_hier_class"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "causal_hypothesis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("deterministic_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("invalid_reference_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_removed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generator_version", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("truncation_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("context_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hyp_runs_analysis",
        "causal_hypothesis_runs",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )

    op.create_table(
        "causal_hypotheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_key", sa.String(length=32), nullable=False),
        sa.Column("rank_placeholder", sa.Integer(), nullable=False),
        sa.Column("category_code", sa.String(length=64), nullable=True),
        sa.Column("level_1_code", sa.String(length=64), nullable=True),
        sa.Column("level_2_code", sa.String(length=64), nullable=True),
        sa.Column("level_3_code", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("causal_claim", sa.Text(), nullable=False),
        sa.Column("root_cause_node_id", sa.String(length=128), nullable=True),
        sa.Column("observed_failure_node_id", sa.String(length=128), nullable=True),
        sa.Column("affected_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("affected_artifact_type", sa.String(length=64), nullable=True),
        sa.Column("affected_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("generator_type", sa.String(length=40), nullable=False),
        sa.Column("generator_name", sa.String(length=64), nullable=False),
        sa.Column("generator_version", sa.String(length=40), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=True),
        sa.Column("template_id", sa.String(length=128), nullable=True),
        sa.Column("generation_confidence", sa.Float(), nullable=False),
        sa.Column("generation_prior_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("path_validation_status", sa.String(length=40), nullable=False),
        sa.Column("path_validation_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("causal_path_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("causal_path_edge_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_observations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("falsifying_observations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_verification_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedupe_fingerprint", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_run_id"], ["causal_hypothesis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hypothesis_run_id",
            "hypothesis_key",
            name="uq_causal_hypotheses_run_key",
        ),
        sa.UniqueConstraint(
            "hypothesis_run_id",
            "rank_placeholder",
            name="uq_causal_hypotheses_run_rank",
        ),
    )
    op.create_index("ix_causal_hyp_analysis", "causal_hypotheses", ["organization_id", "analysis_run_id"])
    op.create_index("ix_causal_hyp_status", "causal_hypotheses", ["status"])
    op.create_index("ix_causal_hyp_category", "causal_hypotheses", ["category_code"])
    op.create_index("ix_causal_hyp_root_node", "causal_hypotheses", ["root_cause_node_id"])
    op.create_index(
        "ix_causal_hyp_dedupe",
        "causal_hypotheses",
        ["hypothesis_run_id", "dedupe_fingerprint"],
        unique=False,
    )

    op.create_table(
        "hypothesis_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_item_id", sa.String(length=128), nullable=True),
        sa.Column("graph_node_id", sa.String(length=128), nullable=True),
        sa.Column("graph_edge_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_id", sa.String(length=128), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("relation", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hyp_evidence_hyp", "hypothesis_evidence_links", ["hypothesis_id"])
    op.create_index("ix_hyp_evidence_rel", "hypothesis_evidence_links", ["relation"])

    op.create_table(
        "hypothesis_critic_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=40), nullable=False),
        sa.Column("recommended_status", sa.String(length=40), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("contradictions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unsupported_claims", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("temporal_conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("specificity_warning", sa.Text(), nullable=True),
        sa.Column("critic_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hypothesis_id", name="uq_hypothesis_critic_hypothesis"),
    )


def downgrade() -> None:
    op.drop_table("hypothesis_critic_results")
    op.drop_table("hypothesis_evidence_links")
    op.drop_table("causal_hypotheses")
    op.drop_table("causal_hypothesis_runs")
