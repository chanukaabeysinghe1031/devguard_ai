"""Reporting, notifications, and audit — additive tables ``incident_reports``,
``notifications``, and ``audit_logs`` plus their enum types.

Option B note
-------------
This wave is purely additive, so there are no transformative drops of legacy
tables. Under Option B the local development database is recreated empty before
``alembic upgrade head``; these tables simply come up empty and are populated by
the application/seed scripts later.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005_reports_notifications_audit"
down_revision: str | None = "004_analysis_run_architecture"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_type_enum = postgresql.ENUM(
    "incident_created",
    "analysis_completed",
    "analysis_failed",
    "assignment",
    "system",
    name="notification_type",
    create_type=False,
)
delivery_status_enum = postgresql.ENUM(
    "pending", "sent", "failed", "read", name="delivery_status", create_type=False
)
generation_status_enum = postgresql.ENUM(
    "pending",
    "generating",
    "completed",
    "failed",
    name="generation_status",
    create_type=False,
)

_NEW_ENUM_OBJECTS = [notification_type_enum, delivery_status_enum, generation_status_enum]


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _NEW_ENUM_OBJECTS:
        postgresql.ENUM(*enum.enums, name=enum.name).create(bind, checkfirst=True)

    op.create_table(
        "incident_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "generation_status",
            generation_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::generation_status"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_reports_incident_id", "incident_reports", ["incident_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notification_type", notification_type_enum, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column(
            "delivery_status",
            delivery_status_enum,
            nullable=False,
            server_default=sa.text("'pending'::delivery_status"),
        ),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_id_is_read_created_at",
        "notifications",
        ["user_id", "is_read", "created_at"],
    )
    op.create_index("ix_notifications_incident_id", "notifications", ["incident_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index(
        "ix_audit_logs_resource_type_resource_id",
        "audit_logs",
        ["resource_type", "resource_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_audit_logs_resource_type_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_notifications_incident_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id_is_read_created_at", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_incident_reports_incident_id", table_name="incident_reports")
    op.drop_table("incident_reports")

    for enum in reversed(_NEW_ENUM_OBJECTS):
        postgresql.ENUM(*enum.enums, name=enum.name).drop(bind, checkfirst=True)
