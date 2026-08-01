# ruff: noqa: E501
"""Migration 016 — Phase 6A.6 counterfactual remediation foundation persistence.

Additive only. No historical backfill. Feature flags default off.
Does not imply verified or applied remediations.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "016_phase6a6_cf_foundation"
down_revision: str | None = "015_phase6a5_hyp_retrieval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "counterfactual_remediation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_ranking_run_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "selected_hypothesis_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("selected_hypothesis_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incomplete_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("context_version", sa.String(length=64), nullable=False),
        sa.Column("constraint_version", sa.String(length=64), nullable=False),
        sa.Column("planner_version", sa.String(length=64), nullable=False),
        sa.Column("template_registry_version", sa.String(length=64), nullable=False),
        sa.Column("snapshot_version", sa.String(length=64), nullable=False),
        sa.Column(
            "configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cf_rem_runs_analysis",
        "counterfactual_remediation_runs",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )
    op.create_index("ix_cf_rem_runs_status", "counterfactual_remediation_runs", ["status"])

    op.create_table(
        "counterfactual_remediation_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_key", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column("category_code", sa.String(length=64), nullable=True),
        sa.Column("affected_artifact_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("primary_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("target_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "current_state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "counterfactual_state_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("expected_effects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "expected_preserved_behaviors", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "expected_failure_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rollback_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("blast_radius_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generator_type", sa.String(length=64), nullable=True),
        sa.Column("generator_name", sa.String(length=128), nullable=True),
        sa.Column("generator_version", sa.String(length=64), nullable=True),
        sa.Column("template_id", sa.String(length=128), nullable=True),
        sa.Column("template_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
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
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "remediation_run_id",
            "candidate_key",
            name="uq_cf_rem_candidate_run_key",
        ),
    )
    op.create_index(
        "ix_cf_rem_cand_analysis",
        "counterfactual_remediation_candidates",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index(
        "ix_cf_rem_cand_hypothesis", "counterfactual_remediation_candidates", ["hypothesis_id"]
    )
    op.create_index("ix_cf_rem_cand_status", "counterfactual_remediation_candidates", ["status"])
    op.create_index(
        "ix_cf_rem_cand_artifact",
        "counterfactual_remediation_candidates",
        ["artifact_type"],
    )

    op.create_table(
        "counterfactual_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_id", sa.String(length=128), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("target_entity_id", sa.String(length=255), nullable=True),
        sa.Column("target_property", sa.String(length=255), nullable=True),
        sa.Column("original_fragment", sa.Text(), nullable=True),
        sa.Column("proposed_fragment", sa.Text(), nullable=True),
        sa.Column("normalized_diff", sa.Text(), nullable=True),
        sa.Column("expected_effect", sa.Text(), nullable=True),
        sa.Column("expected_failure_condition_removed", sa.Boolean(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_edge_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash_before", sa.String(length=128), nullable=True),
        sa.Column("content_hash_after_candidate", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cf_changes_candidate", "counterfactual_changes", ["candidate_id"])
    op.create_index("ix_cf_changes_artifact", "counterfactual_changes", ["artifact_type"])

    op.create_table(
        "remediation_constraints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("constraint_key", sa.String(length=128), nullable=False),
        sa.Column("constraint_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("source_graph_node_id", sa.String(length=128), nullable=True),
        sa.Column("source_graph_edge_id", sa.String(length=128), nullable=True),
        sa.Column("source_evidence_id", sa.String(length=128), nullable=True),
        sa.Column("source_path", sa.String(length=500), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("machine_readable_rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prohibited_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("scope", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("extraction_method", sa.String(length=64), nullable=False),
        sa.Column("extractor_version", sa.String(length=64), nullable=False),
        sa.Column("is_blocking", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_satisfied", sa.Boolean(), nullable=True),
        sa.Column("satisfaction_status", sa.String(length=40), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cf_constraints_analysis",
        "remediation_constraints",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index("ix_cf_constraints_hypothesis", "remediation_constraints", ["hypothesis_id"])
    op.create_index("ix_cf_constraints_candidate", "remediation_constraints", ["candidate_id"])

    op.create_table(
        "remediation_preconditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hypothesis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("condition_type", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_current_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("actual_current_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_node_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hypothesis_id"], ["causal_hypotheses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cf_precond_analysis",
        "remediation_preconditions",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index("ix_cf_precond_hypothesis", "remediation_preconditions", ["hypothesis_id"])

    op.create_table(
        "remediation_verification_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requirement_key", sa.String(length=128), nullable=False),
        sa.Column("verifier_type", sa.String(length=64), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_check", sa.Text(), nullable=True),
        sa.Column("expected_success_condition", sa.Text(), nullable=True),
        sa.Column("blocking_on_failure", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("input_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "requirement_key",
            name="uq_cf_verif_req_candidate_key",
        ),
    )
    op.create_index(
        "ix_cf_verif_req_candidate",
        "remediation_verification_requirements",
        ["candidate_id"],
    )

    op.create_table(
        "remediation_risk_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("risk_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("affected_artifact", sa.String(length=255), nullable=True),
        sa.Column("affected_resource", sa.String(length=255), nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraint_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column("limitations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cf_risk_candidate", "remediation_risk_signals", ["candidate_id"])
    op.create_index("ix_cf_risk_type", "remediation_risk_signals", ["risk_type"])


def downgrade() -> None:
    op.drop_table("remediation_risk_signals")
    op.drop_table("remediation_verification_requirements")
    op.drop_table("remediation_preconditions")
    op.drop_table("remediation_constraints")
    op.drop_table("counterfactual_changes")
    op.drop_table("counterfactual_remediation_candidates")
    op.drop_table("counterfactual_remediation_runs")
