# ruff: noqa: E501
"""Migration 017 — Phase 6A.6 Part 2 counterfactual generation columns.

Additive only. No historical backfill. Feature flags default off.
Does not imply verified or applied remediations.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "017_phase6a6_cf_generation"
down_revision: str | None = "016_phase6a6_cf_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("rendered_patch", sa.Text(), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("patch_format", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("patch_hash", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("changed_file_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("changed_line_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("risk_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("risk_level", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("blast_radius", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("priority_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("priority_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("deduplication_fingerprint", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("validation_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("constraint_status", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column("prompt_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column(
            "side_effects_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column(
            "quality_components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column(
            "risk_components_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "counterfactual_remediation_candidates",
        sa.Column(
            "generation_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_index(
        "ix_cf_rem_cand_priority_status",
        "counterfactual_remediation_candidates",
        ["priority_status"],
    )
    op.create_index(
        "ix_cf_rem_cand_risk_level",
        "counterfactual_remediation_candidates",
        ["risk_level"],
    )
    op.create_index(
        "ix_cf_rem_cand_dedupe_fp",
        "counterfactual_remediation_candidates",
        ["deduplication_fingerprint"],
    )
    op.create_index(
        "ix_cf_rem_cand_generator_type",
        "counterfactual_remediation_candidates",
        ["generator_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cf_rem_cand_generator_type",
        table_name="counterfactual_remediation_candidates",
    )
    op.drop_index(
        "ix_cf_rem_cand_dedupe_fp",
        table_name="counterfactual_remediation_candidates",
    )
    op.drop_index(
        "ix_cf_rem_cand_risk_level",
        table_name="counterfactual_remediation_candidates",
    )
    op.drop_index(
        "ix_cf_rem_cand_priority_status",
        table_name="counterfactual_remediation_candidates",
    )
    for col in (
        "generation_provenance",
        "risk_components_json",
        "quality_components_json",
        "side_effects_json",
        "prompt_version",
        "constraint_status",
        "validation_status",
        "deduplication_fingerprint",
        "priority_status",
        "priority_score",
        "blast_radius",
        "risk_level",
        "risk_score",
        "changed_line_count",
        "changed_file_count",
        "patch_hash",
        "patch_format",
        "rendered_patch",
    ):
        op.drop_column("counterfactual_remediation_candidates", col)
