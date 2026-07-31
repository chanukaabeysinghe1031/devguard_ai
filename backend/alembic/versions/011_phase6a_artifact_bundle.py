"""Migration 011 — Phase 6A.1 artifact bundles and structured parse results.

Additive only. Does not backfill historical incidents. Feature flags default off;
existing analysis behaviour is unchanged when flags are disabled.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "011_phase6a_artifact_bundle"
down_revision: str | None = "010_phase5c_org_tenancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_artifact_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("repository", sa.String(length=300), nullable=True),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("workflow_name", sa.String(length=255), nullable=True),
        sa.Column("workflow_run_id", sa.String(length=64), nullable=True),
        sa.Column("available_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_artifacts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("collection_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("redaction_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bundle_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_artifact_bundles_org_incident",
        "analysis_artifact_bundles",
        ["organization_id", "incident_id"],
    )
    op.create_index(
        "ix_analysis_artifact_bundles_analysis_run_id",
        "analysis_artifact_bundles",
        ["analysis_run_id"],
    )

    op.create_table(
        "analysis_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_kind", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("acquisition_status", sa.String(length=40), nullable=False),
        sa.Column("redaction_status", sa.String(length=40), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(length=40), nullable=True),
        sa.Column("artifact_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["analysis_artifact_bundles.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["uploaded_file_id"], ["uploaded_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_artifacts_bundle_kind",
        "analysis_artifacts",
        ["bundle_id", "artifact_kind"],
    )
    op.create_index(
        "ix_analysis_artifacts_organization_id",
        "analysis_artifacts",
        ["organization_id"],
    )

    op.create_table(
        "artifact_parse_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parser_name", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relationships", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extraction_quality", sa.Float(), nullable=True),
        sa.Column("raw_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["analysis_artifacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_artifact_parse_results_artifact_id",
        "artifact_parse_results",
        ["artifact_id"],
    )
    op.create_index(
        "ix_artifact_parse_results_organization_id",
        "artifact_parse_results",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_parse_results_organization_id", table_name="artifact_parse_results")
    op.drop_index("ix_artifact_parse_results_artifact_id", table_name="artifact_parse_results")
    op.drop_table("artifact_parse_results")
    op.drop_index("ix_analysis_artifacts_organization_id", table_name="analysis_artifacts")
    op.drop_index("ix_analysis_artifacts_bundle_kind", table_name="analysis_artifacts")
    op.drop_table("analysis_artifacts")
    op.drop_index(
        "ix_analysis_artifact_bundles_analysis_run_id",
        table_name="analysis_artifact_bundles",
    )
    op.drop_index(
        "ix_analysis_artifact_bundles_org_incident",
        table_name="analysis_artifact_bundles",
    )
    op.drop_table("analysis_artifact_bundles")
