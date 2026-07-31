"""Migration 010 — Phase 5C multi-tenant completeness (ADR-013).

Extends organization profile fields, adds link-based invitations, and
denormalizes ``organization_id`` onto high-volume tenant rows for simpler
authorization and faster org-scoped queries. Existing data is backfilled from
project / installation joins. No volume wipe required.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "010_phase5c_org_tenancy"
down_revision: str | None = "009_github_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

invitation_status = postgresql.ENUM(
    "pending",
    "accepted",
    "revoked",
    "expired",
    name="invitation_status",
    create_type=False,
)


def upgrade() -> None:
    invitation_status.create(op.get_bind(), checkfirst=True)

    # --- organizations profile ---
    op.add_column("organizations", sa.Column("company_name", sa.String(length=200), nullable=True))
    op.add_column("organizations", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("website", sa.String(length=500), nullable=True))
    op.add_column("organizations", sa.Column("industry", sa.String(length=120), nullable=True))
    op.add_column("organizations", sa.Column("country", sa.String(length=120), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("timezone", sa.String(length=80), server_default="UTC", nullable=False),
    )
    op.add_column("organizations", sa.Column("logo_url", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE organizations SET company_name = name WHERE company_name IS NULL"
        )
    )

    # --- organization_members ---
    op.add_column(
        "organization_members",
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_organization_members_invited_by_users",
        "organization_members",
        "users",
        ["invited_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- organization_invitations ---
    op.create_table(
        "organization_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(
                "organization_owner",
                "organization_admin",
                "engineer",
                "viewer",
                name="organization_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            invitation_status,
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("invited_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_organization_invitations_token_hash"),
    )
    op.create_index(
        "ix_organization_invitations_organization_id",
        "organization_invitations",
        ["organization_id"],
    )
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"])
    op.create_index(
        "ix_organization_invitations_org_status",
        "organization_invitations",
        ["organization_id", "status"],
    )

    # --- incidents.organization_id ---
    op.add_column(
        "incidents",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE incidents AS i
            SET organization_id = p.organization_id
            FROM projects AS p
            WHERE i.project_id = p.id
              AND i.organization_id IS NULL
            """
        )
    )
    op.alter_column("incidents", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_incidents_organization_id_organizations",
        "incidents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_incidents_organization_id_created_at",
        "incidents",
        ["organization_id", "created_at"],
    )
    op.create_index(
        "ix_incidents_organization_id_status",
        "incidents",
        ["organization_id", "status"],
    )

    # --- incident_events.organization_id ---
    op.add_column(
        "incident_events",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE incident_events AS e
            SET organization_id = i.organization_id
            FROM incidents AS i
            WHERE e.incident_id = i.id
              AND e.organization_id IS NULL
            """
        )
    )
    op.alter_column("incident_events", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_incident_events_organization_id_organizations",
        "incident_events",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_incident_events_organization_id_occurred_at",
        "incident_events",
        ["organization_id", "occurred_at"],
    )

    # --- notifications.organization_id (nullable for legacy non-incident rows) ---
    op.add_column(
        "notifications",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE notifications AS n
            SET organization_id = i.organization_id
            FROM incidents AS i
            WHERE n.incident_id = i.id
              AND n.organization_id IS NULL
            """
        )
    )
    op.create_foreign_key(
        "fk_notifications_organization_id_organizations",
        "notifications",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_notifications_organization_id_user_id_created_at",
        "notifications",
        ["organization_id", "user_id", "created_at"],
    )

    # --- webhook_deliveries.organization_id ---
    op.add_column(
        "webhook_deliveries",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE webhook_deliveries AS w
            SET organization_id = gi.organization_id
            FROM github_installations AS gi
            WHERE w.installation_id = gi.github_installation_id
              AND w.organization_id IS NULL
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE webhook_deliveries AS w
            SET organization_id = i.organization_id
            FROM incidents AS i
            WHERE w.related_incident_id = i.id
              AND w.organization_id IS NULL
            """
        )
    )
    op.create_foreign_key(
        "fk_webhook_deliveries_organization_id_organizations",
        "webhook_deliveries",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_webhook_deliveries_organization_id_received_at",
        "webhook_deliveries",
        ["organization_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_deliveries_organization_id_received_at",
        table_name="webhook_deliveries",
    )
    op.drop_constraint(
        "fk_webhook_deliveries_organization_id_organizations",
        "webhook_deliveries",
        type_="foreignkey",
    )
    op.drop_column("webhook_deliveries", "organization_id")

    op.drop_index(
        "ix_notifications_organization_id_user_id_created_at",
        table_name="notifications",
    )
    op.drop_constraint(
        "fk_notifications_organization_id_organizations",
        "notifications",
        type_="foreignkey",
    )
    op.drop_column("notifications", "organization_id")

    op.drop_index(
        "ix_incident_events_organization_id_occurred_at",
        table_name="incident_events",
    )
    op.drop_constraint(
        "fk_incident_events_organization_id_organizations",
        "incident_events",
        type_="foreignkey",
    )
    op.drop_column("incident_events", "organization_id")

    op.drop_index("ix_incidents_organization_id_status", table_name="incidents")
    op.drop_index("ix_incidents_organization_id_created_at", table_name="incidents")
    op.drop_constraint(
        "fk_incidents_organization_id_organizations",
        "incidents",
        type_="foreignkey",
    )
    op.drop_column("incidents", "organization_id")

    op.drop_index("ix_organization_invitations_org_status", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_email", table_name="organization_invitations")
    op.drop_index(
        "ix_organization_invitations_organization_id",
        table_name="organization_invitations",
    )
    op.drop_table("organization_invitations")

    op.drop_constraint(
        "fk_organization_members_invited_by_users",
        "organization_members",
        type_="foreignkey",
    )
    op.drop_column("organization_members", "invited_by")

    op.drop_column("organizations", "logo_url")
    op.drop_column("organizations", "timezone")
    op.drop_column("organizations", "country")
    op.drop_column("organizations", "industry")
    op.drop_column("organizations", "website")
    op.drop_column("organizations", "description")
    op.drop_column("organizations", "company_name")

    invitation_status.drop(op.get_bind(), checkfirst=True)
