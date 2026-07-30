"""Migration 009 — automated GitHub Actions incident ingestion (ADR-005).

Adds the org-level GitHub App installation registry, the repository → project
connection table with automation flags, and the idempotent webhook delivery
ledger. Also relaxes ``uploaded_files.user_id`` so system ingestion can persist
downloaded workflow logs without a human uploader, and prevents duplicate
pipeline runs for the same external CI run.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009_github_ingestion"
down_revision: str | None = "008_refresh_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "github_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_installation_id", sa.BigInteger(), nullable=False),
        sa.Column("github_account_id", sa.BigInteger(), nullable=True),
        sa.Column("github_account_login", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=40), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("permissions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("repository_selection", sa.String(length=40), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "github_installation_id",
            name="uq_github_installations_github_installation_id",
        ),
    )
    op.create_index(
        "ix_github_installations_organization_id",
        "github_installations",
        ["organization_id"],
    )

    op.create_table(
        "github_repository_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("github_repository_id", sa.BigInteger(), nullable=False),
        sa.Column("repository_full_name", sa.String(length=500), nullable=False),
        sa.Column("repository_url", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "is_paused",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "auto_create_incidents",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "auto_start_analysis",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "notify_on_failure",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("workflow_filters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("branch_filters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "failure_conclusions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "environment_mapping_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("severity_rules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_webhook_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["github_installation_id"],
            ["github_installations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_github_repository_connections_github_repository_id",
        "github_repository_connections",
        ["github_repository_id"],
    )
    op.create_index(
        "ix_github_repository_connections_project_id",
        "github_repository_connections",
        ["project_id"],
    )
    op.create_index(
        "ix_github_repository_connections_installation_id",
        "github_repository_connections",
        ["github_installation_id"],
    )
    # One live connection per repository within an organization, and one live
    # GitHub connection per project (MVP scope per ADR-005).
    op.execute(
        """
        CREATE UNIQUE INDEX uq_github_connection_active_repository
        ON github_repository_connections (organization_id, github_repository_id)
        WHERE disconnected_at IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_github_connection_active_project
        ON github_repository_connections (project_id)
        WHERE disconnected_at IS NULL
        """
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=40),
            server_default=sa.text("'github'"),
            nullable=False,
        ),
        sa.Column("delivery_id", sa.String(length=128), nullable=False),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("event_action", sa.String(length=80), nullable=True),
        sa.Column("installation_id", sa.BigInteger(), nullable=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("sanitised_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("processing_status", sa.String(length=40), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message_sanitized", sa.Text(), nullable=True),
        sa.Column("related_pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("related_incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["related_pipeline_run_id"],
            ["pipeline_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["related_incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "delivery_id", name="uq_webhook_deliveries_provider_id"),
    )
    op.create_index(
        "ix_webhook_deliveries_repository_id_received_at",
        "webhook_deliveries",
        ["repository_id", "received_at"],
    )
    op.create_index(
        "ix_webhook_deliveries_processing_status",
        "webhook_deliveries",
        ["processing_status"],
    )

    # System (GitHub) ingestion persists logs without a human uploader.
    op.alter_column("uploaded_files", "user_id", existing_type=postgresql.UUID(), nullable=True)

    # Duplicate webhook protection at the database level.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_pipeline_runs_project_provider_external_run
        ON pipeline_runs (project_id, provider, external_run_id)
        WHERE external_run_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_pipeline_runs_project_provider_external_run")
    op.alter_column("uploaded_files", "user_id", existing_type=postgresql.UUID(), nullable=False)

    op.drop_index("ix_webhook_deliveries_processing_status", table_name="webhook_deliveries")
    op.drop_index(
        "ix_webhook_deliveries_repository_id_received_at",
        table_name="webhook_deliveries",
    )
    op.drop_table("webhook_deliveries")

    op.execute("DROP INDEX IF EXISTS uq_github_connection_active_project")
    op.execute("DROP INDEX IF EXISTS uq_github_connection_active_repository")
    op.drop_index(
        "ix_github_repository_connections_installation_id",
        table_name="github_repository_connections",
    )
    op.drop_index(
        "ix_github_repository_connections_project_id",
        table_name="github_repository_connections",
    )
    op.drop_index(
        "ix_github_repository_connections_github_repository_id",
        table_name="github_repository_connections",
    )
    op.drop_table("github_repository_connections")

    op.drop_index("ix_github_installations_organization_id", table_name="github_installations")
    op.drop_table("github_installations")
