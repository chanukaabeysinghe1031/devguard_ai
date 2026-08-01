# ruff: noqa: E501
"""Migration 018 — Phase 6A.6 Part 3 independent verifier persistence.

Additive only. No historical backfill. Feature flags default off.
Stores temporary-workspace verifier outcomes only — never applied remediations.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "018_phase6a6_verifiers"
down_revision: str | None = "017_phase6a6_cf_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remediation_verification_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("remediation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("consensus_status", sa.String(length=40), nullable=True),
        sa.Column(
            "configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("consensus_version", sa.String(length=64), nullable=True),
        sa.Column("workspace_version", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["remediation_run_id"],
            ["counterfactual_remediation_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "analysis_run_id",
            "candidate_id",
            name="uq_rem_verif_run_org_analysis_candidate",
        ),
    )
    op.create_index(
        "ix_rem_verif_runs_analysis",
        "remediation_verification_runs",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index(
        "ix_rem_verif_runs_status",
        "remediation_verification_runs",
        ["status"],
    )
    op.create_index(
        "ix_rem_verif_runs_consensus",
        "remediation_verification_runs",
        ["consensus_status"],
    )

    op.create_table(
        "remediation_verification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("verifier_name", sa.String(length=128), nullable=False),
        sa.Column("verifier_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stdout_truncated", sa.Text(), nullable=True),
        sa.Column("stderr_truncated", sa.Text(), nullable=True),
        sa.Column("artifacts_checked", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_available", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("returncode", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
            ["verification_run_id"],
            ["remediation_verification_runs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["counterfactual_remediation_candidates.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "verification_run_id",
            "verifier_name",
            name="uq_rem_verif_result_run_name",
        ),
    )
    op.create_index(
        "ix_rem_verif_results_run",
        "remediation_verification_results",
        ["verification_run_id"],
    )
    op.create_index(
        "ix_rem_verif_results_analysis",
        "remediation_verification_results",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index(
        "ix_rem_verif_results_verifier",
        "remediation_verification_results",
        ["verifier_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_rem_verif_results_verifier", table_name="remediation_verification_results")
    op.drop_index("ix_rem_verif_results_analysis", table_name="remediation_verification_results")
    op.drop_index("ix_rem_verif_results_run", table_name="remediation_verification_results")
    op.drop_table("remediation_verification_results")
    op.drop_index("ix_rem_verif_runs_consensus", table_name="remediation_verification_runs")
    op.drop_index("ix_rem_verif_runs_status", table_name="remediation_verification_runs")
    op.drop_index("ix_rem_verif_runs_analysis", table_name="remediation_verification_runs")
    op.drop_table("remediation_verification_runs")
