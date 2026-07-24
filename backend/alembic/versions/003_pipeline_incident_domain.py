"""Pipeline and incident domain — rebuild ``pipeline_runs`` and ``uploaded_files``
in their target shapes and introduce the incident core (``incidents`` and its
timeline/notes/assignments/resolutions children).

Option B note
-------------
Under Option B (SCHEMA_EVOLUTION_PLAN.md §6, ADR-012) the local development
database is recreated empty before ``alembic upgrade head``. The shape change for
``pipeline_runs`` (ownership moves from user to project; status enum replaced) and
``uploaded_files`` (new project/pipeline/incident links and status machine) is
large enough that a **safe recreate** of the empty legacy tables is preferred over
fragile column-by-column transforms. The legacy AI tables that depend on the old
``pipeline_runs`` (``predictions``, ``evidence_items``, ``recommendations``,
``feedback``, ``analysis_history``) are dropped here and rebuilt with
analysis-run roots in Migration 004. Downgrades restore the legacy shapes, but
Option B environments should prefer recreate over downgrade for this wave.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_pipeline_incident_domain"
down_revision: str | None = "002_org_project_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reused from Migration 002.
ci_provider_enum = postgresql.ENUM(
    "github_actions", "gitlab", "jenkins", "other", name="ci_provider", create_type=False
)

# New enum types introduced by this migration.
file_type_enum = postgresql.ENUM(
    "log",
    "workflow_yaml",
    "terraform",
    "json",
    "zip",
    "other",
    name="file_type",
    create_type=False,
)
pipeline_run_status_enum = postgresql.ENUM(
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    name="pipeline_run_status",
    create_type=False,
)
file_validation_status_enum = postgresql.ENUM(
    "pending", "valid", "invalid", "failed", name="file_validation_status", create_type=False
)
secret_masking_status_enum = postgresql.ENUM(
    "pending",
    "masked",
    "failed",
    "not_required",
    name="secret_masking_status",
    create_type=False,
)
file_processing_status_enum = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="file_processing_status",
    create_type=False,
)
incident_status_enum = postgresql.ENUM(
    "detected",
    "analysing",
    "open",
    "in_progress",
    "resolved",
    "closed",
    "analysis_failed",
    "ignored",
    "false_positive",
    "reopened",
    name="incident_status",
    create_type=False,
)
incident_severity_enum = postgresql.ENUM(
    "critical", "high", "medium", "low", name="incident_severity", create_type=False
)
incident_priority_enum = postgresql.ENUM(
    "urgent", "high", "normal", "low", name="incident_priority", create_type=False
)

# Enums created fresh here (drop on downgrade). ``file_type`` and
# ``pipeline_run_status`` also need the legacy variants removed first (upgrade)
# and restored (downgrade).
_NEW_ENUM_OBJECTS = [
    file_type_enum,
    pipeline_run_status_enum,
    file_validation_status_enum,
    secret_masking_status_enum,
    file_processing_status_enum,
    incident_status_enum,
    incident_severity_enum,
    incident_priority_enum,
]

# Legacy enum definitions (for downgrade restoration).
_LEGACY_FILE_TYPE = postgresql.ENUM("log", "workflow_yaml", "terraform", "other", name="file_type")
_LEGACY_PIPELINE_RUN_STATUS = postgresql.ENUM(
    "pending", "processing", "completed", "failed", name="pipeline_run_status"
)


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Drop legacy AI tables that hang off the old pipeline_runs. They are
    #    rebuilt with analysis-run roots in Migration 004.
    # ------------------------------------------------------------------
    op.drop_table("feedback")
    op.drop_table("analysis_history")
    op.drop_table("recommendations")
    op.drop_table("evidence_items")
    op.drop_table("predictions")

    # 2. Drop the legacy pipeline_runs (references uploaded_files) then files.
    op.drop_table("pipeline_runs")
    op.drop_table("uploaded_files")

    # 3. Replace the legacy file_type / pipeline_run_status enums (evidence_type
    #    and risk_level are identical to target and are retained for reuse in 004).
    _LEGACY_FILE_TYPE.drop(bind, checkfirst=True)
    _LEGACY_PIPELINE_RUN_STATUS.drop(bind, checkfirst=True)
    for enum in _NEW_ENUM_OBJECTS:
        postgresql.ENUM(*enum.enums, name=enum.name).create(bind, checkfirst=True)

    # ------------------------------------------------------------------
    # 4. pipeline_runs (project-owned; no direct user ownership).
    # ------------------------------------------------------------------
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_run_id", sa.String(length=255), nullable=True),
        sa.Column("provider", ci_provider_enum, nullable=False),
        sa.Column("workflow_name", sa.String(length=255), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=100), nullable=True),
        sa.Column("triggered_by", sa.String(length=255), nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            pipeline_run_status_enum,
            nullable=False,
            server_default=sa.text("'queued'::pipeline_run_status"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pipeline_runs_project_id_created_at",
        "pipeline_runs",
        ["project_id", "created_at"],
    )
    op.create_index("ix_pipeline_runs_project_id_status", "pipeline_runs", ["project_id", "status"])
    op.create_index(
        "ix_pipeline_runs_provider_external_run_id",
        "pipeline_runs",
        ["provider", "external_run_id"],
    )

    # ------------------------------------------------------------------
    # 5. uploaded_files. The incident_id FK is added after ``incidents`` exists.
    # ------------------------------------------------------------------
    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("file_type", file_type_enum, nullable=False),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "secret_masking_status",
            secret_masking_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::secret_masking_status"),
        ),
        sa.Column(
            "validation_status",
            file_validation_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::file_validation_status"),
        ),
        sa.Column(
            "processing_status",
            file_processing_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::file_processing_status"),
        ),
        sa.Column("extracted_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_non_negative"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_uploaded_files_project_id", "uploaded_files", ["project_id"])
    op.create_index("ix_uploaded_files_incident_id", "uploaded_files", ["incident_id"])
    op.create_index("ix_uploaded_files_pipeline_run_id", "uploaded_files", ["pipeline_run_id"])

    # ------------------------------------------------------------------
    # 6. incidents (human-readable sequential incident_number via a sequence).
    #    latest_analysis_run_id column is created here without its FK; the FK to
    #    analysis_runs is added in Migration 004 (use_alter pattern).
    # ------------------------------------------------------------------
    op.execute("CREATE SEQUENCE IF NOT EXISTS incident_number_seq")
    op.create_table(
        "incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "incident_number",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("nextval('incident_number_seq')"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            incident_status_enum,
            nullable=False,
            server_default=sa.text("'detected'::incident_status"),
        ),
        sa.Column("severity", incident_severity_enum, nullable=False),
        sa.Column("priority", incident_priority_enum, nullable=True),
        sa.Column("environment", sa.String(length=50), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latest_analysis_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("root_cause_summary", sa.Text(), nullable=True),
        sa.Column("impact_summary", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_number", name="uq_incidents_incident_number"),
    )
    op.create_index("ix_incidents_project_id_created_at", "incidents", ["project_id", "created_at"])
    op.create_index("ix_incidents_project_id_status", "incidents", ["project_id", "status"])
    op.create_index("ix_incidents_severity_status", "incidents", ["severity", "status"])
    op.create_index(
        "ix_incidents_current_assignee_id_status",
        "incidents",
        ["current_assignee_id", "status"],
    )
    op.create_index("ix_incidents_detected_at", "incidents", ["detected_at"])

    # ------------------------------------------------------------------
    # 7. Incident children.
    # ------------------------------------------------------------------
    op.create_table(
        "incident_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incident_events_incident_id_occurred_at",
        "incident_events",
        ["incident_id", "occurred_at"],
    )

    op.create_table(
        "incident_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_notes_incident_id", "incident_notes", ["incident_id"])

    op.create_table(
        "incident_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_assignments_incident_id", "incident_assignments", ["incident_id"])

    op.create_table(
        "incident_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolution_summary", sa.Text(), nullable=False),
        sa.Column("confirmed_root_cause", sa.Text(), nullable=False),
        sa.Column("resolution_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("prevention_actions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("time_spent_minutes", sa.Integer(), nullable=True),
        sa.Column("ai_recommendation_used", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_resolutions_incident_id", "incident_resolutions", ["incident_id"])

    # ------------------------------------------------------------------
    # 8. Now that incidents exists, wire uploaded_files.incident_id.
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_uploaded_files_incident_id",
        "uploaded_files",
        "incidents",
        ["incident_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint("fk_uploaded_files_incident_id", "uploaded_files", type_="foreignkey")

    op.drop_index("ix_incident_resolutions_incident_id", table_name="incident_resolutions")
    op.drop_table("incident_resolutions")
    op.drop_index("ix_incident_assignments_incident_id", table_name="incident_assignments")
    op.drop_table("incident_assignments")
    op.drop_index("ix_incident_notes_incident_id", table_name="incident_notes")
    op.drop_table("incident_notes")
    op.drop_index("ix_incident_events_incident_id_occurred_at", table_name="incident_events")
    op.drop_table("incident_events")

    op.drop_index("ix_incidents_detected_at", table_name="incidents")
    op.drop_index("ix_incidents_current_assignee_id_status", table_name="incidents")
    op.drop_index("ix_incidents_severity_status", table_name="incidents")
    op.drop_index("ix_incidents_project_id_status", table_name="incidents")
    op.drop_index("ix_incidents_project_id_created_at", table_name="incidents")
    op.drop_table("incidents")
    op.execute("DROP SEQUENCE IF EXISTS incident_number_seq")

    op.drop_index("ix_uploaded_files_pipeline_run_id", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_incident_id", table_name="uploaded_files")
    op.drop_index("ix_uploaded_files_project_id", table_name="uploaded_files")
    op.drop_table("uploaded_files")

    op.drop_index("ix_pipeline_runs_provider_external_run_id", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_project_id_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_project_id_created_at", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    # Drop the target enums introduced here, restoring the legacy file_type /
    # pipeline_run_status variants.
    for enum in reversed(_NEW_ENUM_OBJECTS):
        postgresql.ENUM(*enum.enums, name=enum.name).drop(bind, checkfirst=True)
    _LEGACY_FILE_TYPE.create(bind, checkfirst=True)
    _LEGACY_PIPELINE_RUN_STATUS.create(bind, checkfirst=True)

    # Restore legacy tables (001 shapes) so the chain remains reversible.
    legacy_file_type = postgresql.ENUM(
        "log", "workflow_yaml", "terraform", "other", name="file_type", create_type=False
    )
    legacy_pipeline_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        name="pipeline_run_status",
        create_type=False,
    )
    evidence_type = postgresql.ENUM(
        "log_line",
        "config_snippet",
        "stack_trace",
        "metric",
        name="evidence_type",
        create_type=False,
    )
    risk_level = postgresql.ENUM(
        "low", "medium", "high", "critical", name="risk_level", create_type=False
    )

    op.create_table(
        "uploaded_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("stored_path", sa.String(length=1024), nullable=False),
        sa.Column("file_type", legacy_file_type, nullable=False),
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
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            legacy_pipeline_status,
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
    )
    op.create_index("ix_pipeline_runs_uploaded_file_id", "pipeline_runs", ["uploaded_file_id"])
    op.create_index("ix_pipeline_runs_workflow_file_id", "pipeline_runs", ["workflow_file_id"])

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
        sa.Column("evidence_type", evidence_type, nullable=False),
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
            risk_level,
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
    )
    op.create_index("ix_analysis_history_pipeline_run_id", "analysis_history", ["pipeline_run_id"])
