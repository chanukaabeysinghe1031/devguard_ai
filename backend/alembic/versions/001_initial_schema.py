"""Initial DevGuard AI schema — enums, tables, constraints, and indexes."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Shared PostgreSQL enum types (created once, referenced by multiple tables)
USER_ROLE = postgresql.ENUM(
    "admin", "analyst", "viewer", name="user_role", create_type=False
)
FILE_TYPE = postgresql.ENUM(
    "log", "workflow_yaml", "terraform", "other", name="file_type", create_type=False
)
PIPELINE_RUN_STATUS = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="pipeline_run_status",
    create_type=False,
)
EVIDENCE_TYPE = postgresql.ENUM(
    "log_line",
    "config_snippet",
    "stack_trace",
    "metric",
    name="evidence_type",
    create_type=False,
)
RISK_LEVEL = postgresql.ENUM(
    "low", "medium", "high", "critical", name="risk_level", create_type=False
)

ENUM_TYPES = [
    ("user_role", ("admin", "analyst", "viewer")),
    ("file_type", ("log", "workflow_yaml", "terraform", "other")),
    ("pipeline_run_status", ("pending", "processing", "completed", "failed")),
    ("evidence_type", ("log_line", "config_snippet", "stack_trace", "metric")),
    ("risk_level", ("low", "medium", "high", "critical")),
]


def _create_enums() -> None:
    bind = op.get_bind()
    for name, values in ENUM_TYPES:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)


def _drop_enums() -> None:
    bind = op.get_bind()
    for name, values in reversed(ENUM_TYPES):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            USER_ROLE,
            nullable=False,
            server_default=sa.text("'analyst'::user_role"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

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
    op.create_index("ix_failure_categories_slug", "failure_categories", ["slug"], unique=False)

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
    op.create_index("ix_model_versions_name", "model_versions", ["name"], unique=False)

    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("file_type", FILE_TYPE, nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_uploaded_files_user_id_created_at",
        "uploaded_files",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            PIPELINE_RUN_STATUS,
            nullable=False,
            server_default=sa.text("'pending'::pipeline_run_status"),
        ),
        sa.Column("platform", sa.String(length=64), nullable=False),
        sa.Column("pipeline_name", sa.String(length=255), nullable=True),
        sa.Column("job_name", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_log_excerpt", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["uploaded_file_id"], ["uploaded_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_file_id"], ["uploaded_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_runs_user_id_status_created_at",
        "pipeline_runs",
        ["user_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_pipeline_runs_uploaded_file_id", "pipeline_runs", ["uploaded_file_id"], unique=False
    )
    op.create_index(
        "ix_pipeline_runs_workflow_file_id", "pipeline_runs", ["workflow_file_id"], unique=False
    )

    op.create_table(
        "predictions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("classifier_name", sa.String(length=128), nullable=False),
        sa.Column("feature_vector_hash", sa.String(length=64), nullable=True),
        sa.Column("probabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_predictions_confidence_score_range",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["failure_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["model_version_id"], ["model_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_pipeline_run_id", "predictions", ["pipeline_run_id"])
    op.create_index("ix_predictions_category_id", "predictions", ["category_id"])
    op.create_index("ix_predictions_model_version_id", "predictions", ["model_version_id"])

    op.create_table(
        "evidence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", EVIDENCE_TYPE, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_location", sa.String(length=512), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("highlight_start", sa.Integer(), nullable=True),
        sa.Column("highlight_end", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_evidence_items_relevance_score_range",
        ),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_items_pipeline_run_id", "evidence_items", ["pipeline_run_id"])
    op.create_index("ix_evidence_items_prediction_id", "evidence_items", ["prediction_id"])

    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prediction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("remediation_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "risk_level",
            RISK_LEVEL,
            nullable=False,
            server_default=sa.text("'medium'::risk_level"),
        ),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("preventive_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("future_improvements", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("llm_model", sa.String(length=128), nullable=False),
        sa.Column("rag_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_recommendations_confidence_score_range",
        ),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_pipeline_run_id", "recommendations", ["pipeline_run_id"])
    op.create_index("ix_recommendations_prediction_id", "recommendations", ["prediction_id"])

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

    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("is_helpful", sa.Boolean(), nullable=True),
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
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recommendation_id"], ["recommendations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_pipeline_run_id", "feedback", ["pipeline_run_id"])
    op.create_index("ix_feedback_recommendation_id", "feedback", ["recommendation_id"])

    op.create_table(
        "analysis_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analysis_history_user_id_created_at",
        "analysis_history",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_analysis_history_pipeline_run_id", "analysis_history", ["pipeline_run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_analysis_history_pipeline_run_id", table_name="analysis_history")
    op.drop_index("ix_analysis_history_user_id_created_at", table_name="analysis_history")
    op.drop_table("analysis_history")

    op.drop_index("ix_feedback_recommendation_id", table_name="feedback")
    op.drop_index("ix_feedback_pipeline_run_id", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")

    op.drop_index("ix_evaluations_user_id", table_name="evaluations")
    op.drop_index("ix_evaluations_model_version_id", table_name="evaluations")
    op.drop_table("evaluations")

    op.drop_index("ix_recommendations_prediction_id", table_name="recommendations")
    op.drop_index("ix_recommendations_pipeline_run_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_evidence_items_prediction_id", table_name="evidence_items")
    op.drop_index("ix_evidence_items_pipeline_run_id", table_name="evidence_items")
    op.drop_table("evidence_items")

    op.drop_index("ix_predictions_model_version_id", table_name="predictions")
    op.drop_index("ix_predictions_category_id", table_name="predictions")
    op.drop_index("ix_predictions_pipeline_run_id", table_name="predictions")
    op.drop_table("predictions")

    op.drop_index("ix_pipeline_runs_workflow_file_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_uploaded_file_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_user_id_status_created_at", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_index("ix_uploaded_files_user_id_created_at", table_name="uploaded_files")
    op.drop_table("uploaded_files")

    op.drop_index("ix_model_versions_name", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index("ix_failure_categories_slug", table_name="failure_categories")
    op.drop_table("failure_categories")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    _drop_enums()
