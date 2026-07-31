# ruff: noqa: E501
"""Migration 013 — Phase 6A.3 hierarchical classification and open-set detection.

Additive only. No historical backfill. Feature flags default off.
Revision id kept short for alembic version_num varchar(32).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "013_phase6a3_hier_class"
down_revision: str | None = "012_phase6a2_temporal_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("legacy_category_code", sa.String(length=64), nullable=False),
        sa.Column("level_1_code", sa.String(length=64), nullable=False),
        sa.Column("level_1_label", sa.String(length=128), nullable=False),
        sa.Column("level_2_code", sa.String(length=64), nullable=False),
        sa.Column("level_2_label", sa.String(length=128), nullable=False),
        sa.Column("level_3_code", sa.String(length=64), nullable=False),
        sa.Column("level_3_label", sa.String(length=128), nullable=False),
        sa.Column("mapping_version", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "legacy_category_code",
            "mapping_version",
            name="uq_taxonomy_mappings_code_version",
        ),
    )
    op.create_index("ix_taxonomy_mappings_l1", "taxonomy_mappings", ["level_1_code"])
    op.create_index("ix_taxonomy_mappings_l2", "taxonomy_mappings", ["level_2_code"])
    op.create_index("ix_taxonomy_mappings_l3", "taxonomy_mappings", ["level_3_code"])

    op.create_table(
        "hierarchical_classification_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("final_legacy_category_code", sa.String(length=64), nullable=True),
        sa.Column("level_1_code", sa.String(length=64), nullable=True),
        sa.Column("level_2_code", sa.String(length=64), nullable=True),
        sa.Column("level_3_code", sa.String(length=64), nullable=True),
        sa.Column("classification_status", sa.String(length=40), nullable=False),
        sa.Column("final_confidence", sa.Float(), nullable=True),
        sa.Column("mapping_version", sa.String(length=40), nullable=False),
        sa.Column("model_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rule_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("learned_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("llm_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluation_export", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hier_class_analysis",
        "hierarchical_classification_results",
        ["organization_id", "analysis_run_id"],
        unique=True,
    )
    op.create_index(
        "ix_hier_class_status",
        "hierarchical_classification_results",
        ["classification_status"],
    )
    op.create_index(
        "ix_hier_class_category",
        "hierarchical_classification_results",
        ["final_legacy_category_code"],
    )

    op.create_table(
        "classification_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchical_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_code", sa.String(length=64), nullable=False),
        sa.Column("level_1_code", sa.String(length=64), nullable=True),
        sa.Column("level_2_code", sa.String(length=64), nullable=True),
        sa.Column("level_3_code", sa.String(length=64), nullable=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("source_classifier", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("supporting_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contradicting_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("matched_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hierarchical_result_id"],
            ["hierarchical_classification_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hierarchical_result_id",
            "rank",
            name="uq_classification_candidates_result_rank",
        ),
    )
    op.create_index(
        "ix_class_candidates_analysis",
        "classification_candidates",
        ["organization_id", "analysis_run_id"],
    )
    op.create_index(
        "ix_class_candidates_source",
        "classification_candidates",
        ["source_classifier"],
    )

    op.create_table(
        "open_set_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchical_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("unknown_score", sa.Float(), nullable=False),
        sa.Column("maximum_known_score", sa.Float(), nullable=False),
        sa.Column("top_two_margin", sa.Float(), nullable=False),
        sa.Column("rule_coverage", sa.Float(), nullable=False),
        sa.Column("representation_distance", sa.Float(), nullable=True),
        sa.Column("evidence_coverage", sa.Float(), nullable=False),
        sa.Column("disagreement_level", sa.String(length=40), nullable=True),
        sa.Column("threshold_version", sa.String(length=40), nullable=False),
        sa.Column("triggered_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hierarchical_result_id"],
            ["hierarchical_classification_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hierarchical_result_id",
            name="uq_open_set_assessments_result",
        ),
    )
    op.create_index("ix_open_set_status", "open_set_assessments", ["status"])
    op.create_index(
        "ix_open_set_analysis",
        "open_set_assessments",
        ["organization_id", "analysis_run_id"],
    )

    op.create_table(
        "classification_disagreement_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchical_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agreement_level", sa.String(length=40), nullable=False),
        sa.Column("agreed_level_1", sa.String(length=64), nullable=True),
        sa.Column("agreed_level_2", sa.String(length=64), nullable=True),
        sa.Column("agreed_level_3", sa.String(length=64), nullable=True),
        sa.Column("conflicting_candidates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflict_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_conflict", sa.Boolean(), nullable=False),
        sa.Column("classifier_conflict", sa.Boolean(), nullable=False),
        sa.Column("category_distance", sa.Float(), nullable=False),
        sa.Column("recommended_action", sa.String(length=64), nullable=False),
        sa.Column("additional_evidence_needed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_penalty", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hierarchical_result_id"],
            ["hierarchical_classification_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hierarchical_result_id",
            name="uq_class_disagreement_result",
        ),
    )
    op.create_index(
        "ix_class_disagreement_level",
        "classification_disagreement_results",
        ["agreement_level"],
    )

    op.create_table(
        "classification_confidence_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchical_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_name", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=False),
        sa.Column("normalized_value", sa.Float(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("contribution", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hierarchical_result_id"],
            ["hierarchical_classification_results.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hierarchical_result_id",
            "component_name",
            name="uq_class_confidence_component",
        ),
    )
    op.create_index(
        "ix_class_confidence_analysis",
        "classification_confidence_components",
        ["organization_id", "analysis_run_id"],
    )


def downgrade() -> None:
    op.drop_table("classification_confidence_components")
    op.drop_table("classification_disagreement_results")
    op.drop_table("open_set_assessments")
    op.drop_table("classification_candidates")
    op.drop_table("hierarchical_classification_results")
    op.drop_table("taxonomy_mappings")
