# ruff: noqa: E501
"""Migration 019 — shared GitHub App installations (ADR-005 extension).

Introduces organization-scoped access grants for a GitHub App installation so
that one installation (one GitHub account/org) can be used by many DevGuard
organizations and projects, with repository-scoped tenant isolation. Also
adds a per-connection webhook processing ledger so a single delivery can fan
out to multiple tenants without one tenant's outcome masking another's.

Additive-first and reversible:

- ``github_installations.organization_id`` becomes nullable legacy metadata
  (original linker only) — it is NOT dropped and no rows are deleted.
- All existing installations with an ``organization_id`` are backfilled into
  one ACTIVE ``github_installation_organization_access`` row.
- All existing live repository connections are backfilled with their
  matching ``installation_access_id``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "019_shared_github_installations"
down_revision: str | None = "018_phase6a6_verifiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INSTALLATION_ORG_FK = "github_installations_organization_id_fkey"


def upgrade() -> None:
    # 1. Organization access grant table (global installation identity ->
    #    many DevGuard organizations).
    op.create_table(
        "github_installation_organization_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column("linked_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permissions_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("repository_selection", sa.String(length=40), nullable=True),
        sa.Column("last_repository_sync_at", sa.DateTime(timezone=True), nullable=True),
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
            ["installation_id"],
            ["github_installations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "installation_id",
            "organization_id",
            name="uq_github_install_org_access",
        ),
    )
    op.create_index(
        "ix_github_install_org_access_organization_id",
        "github_installation_organization_access",
        ["organization_id"],
    )
    op.create_index(
        "ix_github_install_org_access_installation_id",
        "github_installation_organization_access",
        ["installation_id"],
    )
    op.create_index(
        "ix_github_install_org_access_status",
        "github_installation_organization_access",
        ["status"],
    )

    # 2. Backfill one ACTIVE access grant per already-linked installation.
    #    No rows are read as authoritative here beyond what already existed.
    op.execute(
        """
        INSERT INTO github_installation_organization_access (
            id,
            installation_id,
            organization_id,
            status,
            linked_at,
            permissions_snapshot,
            repository_selection,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            gi.id,
            gi.organization_id,
            'active',
            COALESCE(gi.installed_at, gi.created_at, now()),
            gi.permissions_json,
            gi.repository_selection,
            now(),
            now()
        FROM github_installations gi
        WHERE gi.organization_id IS NOT NULL
        """
    )

    # 3. Nullable FK column on repository connections pointing at the access
    #    grant the connection was made under (backfilled below).
    op.add_column(
        "github_repository_connections",
        sa.Column("installation_access_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 4. Backfill by joining the connection's own organization_id and
    #    installation id against the freshly created access grants.
    op.execute(
        """
        UPDATE github_repository_connections grc
        SET installation_access_id = access.id
        FROM github_installation_organization_access access
        WHERE access.installation_id = grc.github_installation_id
          AND access.organization_id = grc.organization_id
        """
    )

    # 5. FK + index for the new column.
    op.create_foreign_key(
        "github_repository_connections_installation_access_id_fkey",
        "github_repository_connections",
        "github_installation_organization_access",
        ["installation_access_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_github_repository_connections_installation_access_id",
        "github_repository_connections",
        ["installation_access_id"],
    )

    # 6. Per-connection webhook fan-out processing ledger.
    op.create_table(
        "webhook_delivery_connection_processing",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_delivery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_connection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message_sanitized", sa.Text(), nullable=True),
        sa.Column("pipeline_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
            ["webhook_delivery_id"],
            ["webhook_deliveries.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_connection_id"],
            ["github_repository_connections.id"],
            ondelete="CASCADE",
            name="webhook_delivery_conn_processing_repo_connection_id_fkey",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pipeline_run_id"], ["pipeline_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "webhook_delivery_id",
            "repository_connection_id",
            name="uq_webhook_delivery_connection",
        ),
    )
    op.create_index(
        "ix_webhook_delivery_conn_processing_organization_id",
        "webhook_delivery_connection_processing",
        ["organization_id"],
    )
    op.create_index(
        "ix_webhook_delivery_conn_processing_repo_connection_id",
        "webhook_delivery_connection_processing",
        ["repository_connection_id"],
    )
    op.create_index(
        "ix_webhook_delivery_conn_processing_status",
        "webhook_delivery_connection_processing",
        ["status"],
    )

    # 7. Demote github_installations.organization_id to nullable legacy
    #    metadata. Existing values are preserved; only the constraint and
    #    nullability change.
    op.drop_constraint(_INSTALLATION_ORG_FK, "github_installations", type_="foreignkey")
    op.alter_column(
        "github_installations",
        "organization_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_foreign_key(
        _INSTALLATION_ORG_FK,
        "github_installations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_webhook_delivery_conn_processing_status",
        table_name="webhook_delivery_connection_processing",
    )
    op.drop_index(
        "ix_webhook_delivery_conn_processing_repo_connection_id",
        table_name="webhook_delivery_connection_processing",
    )
    op.drop_index(
        "ix_webhook_delivery_conn_processing_organization_id",
        table_name="webhook_delivery_connection_processing",
    )
    op.drop_table("webhook_delivery_connection_processing")

    op.drop_index(
        "ix_github_repository_connections_installation_access_id",
        table_name="github_repository_connections",
    )
    op.drop_constraint(
        "github_repository_connections_installation_access_id_fkey",
        "github_repository_connections",
        type_="foreignkey",
    )
    op.drop_column("github_repository_connections", "installation_access_id")

    # Best-effort recovery of a single primary organization per installation
    # before the access table disappears. Installs that gained access from
    # more than one organization after upgrade cannot be losslessly reduced
    # to one owner — those are intentionally left with a NULL organization_id.
    op.execute(
        """
        UPDATE github_installations gi
        SET organization_id = sub.organization_id
        FROM (
            SELECT DISTINCT ON (installation_id)
                installation_id,
                organization_id
            FROM github_installation_organization_access
            WHERE status = 'active'
            ORDER BY installation_id, linked_at ASC
        ) sub
        WHERE gi.organization_id IS NULL
          AND gi.id = sub.installation_id
        """
    )

    op.drop_constraint(_INSTALLATION_ORG_FK, "github_installations", type_="foreignkey")

    remaining_nulls = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM github_installations WHERE organization_id IS NULL")
    ).scalar_one()
    if remaining_nulls == 0:
        op.alter_column(
            "github_installations",
            "organization_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=False,
        )

    op.create_foreign_key(
        _INSTALLATION_ORG_FK,
        "github_installations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index(
        "ix_github_install_org_access_status",
        table_name="github_installation_organization_access",
    )
    op.drop_index(
        "ix_github_install_org_access_installation_id",
        table_name="github_installation_organization_access",
    )
    op.drop_index(
        "ix_github_install_org_access_organization_id",
        table_name="github_installation_organization_access",
    )
    op.drop_table("github_installation_organization_access")
