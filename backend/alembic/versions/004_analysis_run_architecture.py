"""Analysis run architecture — introduce ``analysis_runs`` as the AI execution
root and rebuild predictions, evidence, recommendations (+ normalized
``recommendation_steps``), retrieved documents, and feedback around it. Evolve
``failure_categories`` (slug→code), and reshape ``model_versions`` / ``evaluations``
toward the target schema.

Option B note
-------------
Under Option B (SCHEMA_EVOLUTION_PLAN.md §6, ADR-012) the local development
database is recreated empty, so heavily reshaped tables are safely recreated
rather than transformed column-by-column. ``failure_categories``,
``model_versions`` and ``evaluations`` have no dependents at this point (their
legacy children were dropped in Migration 003), so they are dropped and recreated
in their target shapes. The ``retrieved_documents.knowledge_chunk_id`` foreign key
is deferred to Migration 006 (knowledge tables do not exist yet). The
``incidents.latest_analysis_run_id`` foreign key is added here now that
``analysis_runs`` exists (use_alter pattern from the ORM model).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_analysis_run_architecture"
down_revision: str | None = "003_pipeline_incident_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reused from earlier migrations (identical to target values).
evidence_type_enum = postgresql.ENUM(
    "log_line",
    "config_snippet",
    "stack_trace",
    "metric",
    name="evidence_type",
    create_type=False,
)
risk_level_enum = postgresql.ENUM(
    "low", "medium", "high", "critical", name="risk_level", create_type=False
)
incident_severity_enum = postgresql.ENUM(
    "critical", "high", "medium", "low", name="incident_severity", create_type=False
)

# New enum types introduced here.
analysis_run_status_enum = postgresql.ENUM(
    "queued",
    "preprocessing",
    "classifying",
    "retrieving",
    "reasoning",
    "completed",
    "failed",
    name="analysis_run_status",
    create_type=False,
)
recommendation_step_type_enum = postgresql.ENUM(
    "remediation",
    "verification",
    "prevention",
    name="recommendation_step_type",
    create_type=False,
)
model_version_status_enum = postgresql.ENUM(
    "training",
    "active",
    "deprecated",
    "failed",
    name="model_version_status",
    create_type=False,
)

_NEW_ENUM_OBJECTS = [
    analysis_run_status_enum,
    recommendation_step_type_enum,
    model_version_status_enum,
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _NEW_ENUM_OBJECTS:
        postgresql.ENUM(*enum.enums, name=enum.name).create(bind, checkfirst=True)

    # ------------------------------------------------------------------
    # 1. Reshape model_versions and evaluations (recreate — no dependents now).
    # ------------------------------------------------------------------
    op.drop_index("ix_evaluations_user_id", table_name="evaluations")
    op.drop_index("ix_evaluations_model_version_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_model_versions_name", table_name="model_versions")
    op.drop_table("model_versions")

    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_name", sa.String(length=150), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("artifact_path", sa.String(length=1024), nullable=True),
        sa.Column("training_dataset_version", sa.String(length=100), nullable=True),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "status",
            model_version_status_enum,
            nullable=False,
            server_default=sa.text("'training'::model_version_status"),
        ),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name", "version", name="uq_model_versions_model_name_version"),
    )
    op.create_index("ix_model_versions_model_name", "model_versions", ["model_name"])

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evaluation_type", sa.String(length=60), nullable=False),
        sa.Column("dataset_version", sa.String(length=100), nullable=True),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluations_model_version_id", "evaluations", ["model_version_id"])

    # ------------------------------------------------------------------
    # 2. Evolve failure_categories (slug→code; add hierarchy + default_severity).
    #    Recreated because it has no dependents at this point.
    # ------------------------------------------------------------------
    op.drop_index("ix_failure_categories_slug", table_name="failure_categories")
    op.drop_table("failure_categories")
    op.create_table(
        "failure_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_severity", incident_severity_enum, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["failure_categories.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_failure_categories_code"),
    )
    op.create_index("ix_failure_categories_code", "failure_categories", ["code"])

    # ------------------------------------------------------------------
    # 3. analysis_runs — the AI execution root.
    # ------------------------------------------------------------------
    op.create_table(
        "analysis_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            analysis_run_status_enum,
            nullable=False,
            server_default=sa.text("'queued'::analysis_run_status"),
        ),
        sa.Column("analysis_type", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("current_stage", sa.String(length=60), nullable=True),
        sa.Column(
            "progress_percentage",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_runs_incident_id_created_at",
        "analysis_runs",
        ["incident_id", "created_at"],
    )
    op.create_index("ix_analysis_runs_status_created_at", "analysis_runs", ["status", "created_at"])

    # 4. Wire incidents.latest_analysis_run_id → analysis_runs (use_alter pattern).
    op.create_foreign_key(
        "fk_incidents_latest_analysis_run_id",
        "incidents",
        "analysis_runs",
        ["latest_analysis_run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 5. predictions — rooted at analysis_runs.
    # ------------------------------------------------------------------
    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("failure_category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("predicted_label", sa.String(length=150), nullable=False),
        sa.Column("root_cause_summary", sa.Text(), nullable=True),
        sa.Column("technical_explanation", sa.Text(), nullable=True),
        sa.Column("impact_summary", sa.Text(), nullable=True),
        sa.Column("reasoning_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_predictions_confidence_range"
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["failure_category_id"], ["failure_categories.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_run_id", "rank", name="uq_predictions_analysis_run_rank"),
    )

    # ------------------------------------------------------------------
    # 6. evidence_items — rooted at analysis_runs; linked to uploaded files.
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", evidence_type_enum, nullable=False),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
        sa.Column("normalized_excerpt", sa.Text(), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("importance_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_file_id"], ["uploaded_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_items_analysis_run_id", "evidence_items", ["analysis_run_id"])
    op.create_index("ix_evidence_items_prediction_id", "evidence_items", ["prediction_id"])

    # ------------------------------------------------------------------
    # 7. recommendations (parent/summary) — steps live in recommendation_steps.
    # ------------------------------------------------------------------
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("root_cause_summary", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column(
            "legacy_remediation_steps",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment=(
                "Deprecated pre-Migration-004 JSON blob; recommendation_steps is authoritative."
            ),
        ),
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
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_recommendations_confidence_score_range",
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_analysis_run_id", "recommendations", ["analysis_run_id"])
    op.create_index("ix_recommendations_prediction_id", "recommendations", ["prediction_id"])

    # ------------------------------------------------------------------
    # 8. recommendation_steps — normalized ordered steps.
    # ------------------------------------------------------------------
    op.create_table(
        "recommendation_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("step_type", recommendation_step_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("risk_level", risk_level_enum, nullable=True),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("command_template", sa.Text(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "recommendation_id",
            "step_number",
            name="uq_recommendation_steps_recommendation_step",
        ),
    )

    # ------------------------------------------------------------------
    # 9. retrieved_documents — the knowledge_chunk_id FK is added in 006.
    # ------------------------------------------------------------------
    op.create_table(
        "retrieved_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("similarity_score", sa.Numeric(precision=7, scale=6), nullable=True),
        sa.Column(
            "used_in_reasoning",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_retrieved_documents_analysis_run_id",
        "retrieved_documents",
        ["analysis_run_id"],
    )

    # ------------------------------------------------------------------
    # 10. feedback — rooted at incident + analysis_run.
    # ------------------------------------------------------------------
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("analysis_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feedback_type", sa.String(length=40), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("is_useful", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_feedback_rating_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_incident_id", "feedback", ["incident_id"])
    op.create_index("ix_feedback_analysis_run_id", "feedback", ["analysis_run_id"])


def downgrade() -> None:
    bind = op.get_bind()

    # Drop analysis-run-rooted tables (reverse creation order).
    op.drop_index("ix_feedback_analysis_run_id", table_name="feedback")
    op.drop_index("ix_feedback_incident_id", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")

    op.drop_index("ix_retrieved_documents_analysis_run_id", table_name="retrieved_documents")
    op.drop_table("retrieved_documents")

    op.drop_table("recommendation_steps")

    op.drop_index("ix_recommendations_prediction_id", table_name="recommendations")
    op.drop_index("ix_recommendations_analysis_run_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_evidence_items_prediction_id", table_name="evidence_items")
    op.drop_index("ix_evidence_items_analysis_run_id", table_name="evidence_items")
    op.drop_table("evidence_items")

    op.drop_table("predictions")

    op.drop_constraint("fk_incidents_latest_analysis_run_id", "incidents", type_="foreignkey")
    op.drop_index("ix_analysis_runs_status_created_at", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_incident_id_created_at", table_name="analysis_runs")
    op.drop_table("analysis_runs")

    # Restore legacy failure_categories.
    op.drop_index("ix_failure_categories_code", table_name="failure_categories")
    op.drop_table("failure_categories")
    op.create_table(
        "failure_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_failure_categories_slug", "failure_categories", ["slug"])

    # Restore legacy model_versions and evaluations.
    op.drop_index("ix_evaluations_model_version_id", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_index("ix_model_versions_model_name", table_name="model_versions")
    op.drop_table("model_versions")

    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("classifier_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_path", sa.String(length=1024), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("training_dataset_ref", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
    )
    op.create_index("ix_model_versions_name", "model_versions", ["name"])

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluations_model_version_id", "evaluations", ["model_version_id"])
    op.create_index("ix_evaluations_user_id", "evaluations", ["user_id"])

    for enum in reversed(_NEW_ENUM_OBJECTS):
        postgresql.ENUM(*enum.enums, name=enum.name).drop(bind, checkfirst=True)
