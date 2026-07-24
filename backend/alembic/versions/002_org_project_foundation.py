"""Organization and project foundation — organizations, memberships, projects,
integrations, and the evolution of the ``users`` table toward the target schema.

Option B note
-------------
The local development database is recreated empty and then migrated with
``alembic upgrade head`` (SCHEMA_EVOLUTION_PLAN.md §6, ADR-012). Because no
irreplaceable rows exist locally, transformative column changes on ``users``
(rename ``hashed_password`` → ``password_hash``, drop the legacy global ``role``
column and its ``user_role`` enum) are acceptable. The ``UPDATE`` statement that
maps ``role='admin'`` → ``platform_admin`` is a no-op on an empty table but keeps
the migration correct for any non-empty environment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_org_project_foundation"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Enum types introduced by this migration (referenced with create_type=False so
# creation/removal is managed explicitly and idempotently below).
# ---------------------------------------------------------------------------
NEW_ENUMS: list[tuple[str, tuple[str, ...]]] = [
    ("platform_role", ("platform_admin", "none")),
    ("organization_status", ("active", "suspended", "archived")),
    ("organization_role", ("organization_owner", "organization_admin", "engineer", "viewer")),
    ("project_status", ("active", "paused", "archived")),
    ("ci_provider", ("github_actions", "gitlab", "jenkins", "other")),
    ("integration_status", ("active", "disabled", "error")),
]

platform_role_enum = postgresql.ENUM(
    "platform_admin", "none", name="platform_role", create_type=False
)
organization_status_enum = postgresql.ENUM(
    "active", "suspended", "archived", name="organization_status", create_type=False
)
organization_role_enum = postgresql.ENUM(
    "organization_owner",
    "organization_admin",
    "engineer",
    "viewer",
    name="organization_role",
    create_type=False,
)
project_status_enum = postgresql.ENUM(
    "active", "paused", "archived", name="project_status", create_type=False
)
ci_provider_enum = postgresql.ENUM(
    "github_actions", "gitlab", "jenkins", "other", name="ci_provider", create_type=False
)
integration_status_enum = postgresql.ENUM(
    "active", "disabled", "error", name="integration_status", create_type=False
)


def _create_new_enums() -> None:
    bind = op.get_bind()
    for name, values in NEW_ENUMS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)


def _drop_new_enums() -> None:
    bind = op.get_bind()
    for name, values in reversed(NEW_ENUMS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)


def upgrade() -> None:
    _create_new_enums()

    # ------------------------------------------------------------------
    # organizations
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default=sa.text("'mvp'")),
        sa.Column(
            "status",
            organization_status_enum,
            nullable=False,
            server_default=sa.text("'active'::organization_status"),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)

    # ------------------------------------------------------------------
    # organization_members
    # ------------------------------------------------------------------
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", organization_role_enum, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )
    op.create_index(
        "ix_organization_members_organization_id",
        "organization_members",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_members_user_id",
        "organization_members",
        ["user_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("key", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repository_url", sa.Text(), nullable=True),
        sa.Column("default_branch", sa.String(length=120), nullable=True),
        sa.Column("ci_provider", ci_provider_enum, nullable=False),
        sa.Column("cloud_provider", sa.String(length=50), nullable=True),
        sa.Column("default_environment", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            project_status_enum,
            nullable=False,
            server_default=sa.text("'active'::project_status"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_projects_organization_key"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], unique=False)
    op.create_index("ix_projects_created_by", "projects", ["created_by"], unique=False)

    # ------------------------------------------------------------------
    # project_integrations (metadata only — never raw secrets)
    # ------------------------------------------------------------------
    op.create_table(
        "project_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=60), nullable=False),
        sa.Column("integration_type", sa.String(length=60), nullable=False),
        sa.Column("external_reference", sa.Text(), nullable=True),
        sa.Column("configuration", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("encrypted_secret_reference", sa.Text(), nullable=True),
        sa.Column(
            "status",
            integration_status_enum,
            nullable=False,
            server_default=sa.text("'active'::integration_status"),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_integrations_project_id",
        "project_integrations",
        ["project_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # users — evolve toward target schema
    # ------------------------------------------------------------------
    # 1. Rename hashed_password → password_hash.
    op.alter_column("users", "hashed_password", new_column_name="password_hash")
    # 2. Narrow full_name to the target length (safe on empty/short data).
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=255),
        type_=sa.String(length=150),
        existing_nullable=False,
    )
    # 3. Additive profile columns.
    op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    # 4. Platform-level role (not an organization membership role).
    op.add_column(
        "users",
        sa.Column(
            "platform_role",
            platform_role_enum,
            nullable=False,
            server_default=sa.text("'none'::platform_role"),
        ),
    )
    # 5. Map legacy admins to the platform_admin capability (no-op when empty).
    op.execute(
        "UPDATE users SET platform_role = 'platform_admin'::platform_role WHERE role = 'admin'"
    )
    # 6. Drop the legacy global role column and its now-unused enum type.
    op.drop_column("users", "role")
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Recreate the legacy user_role enum and role column.
    user_role_enum = postgresql.ENUM("admin", "analyst", "viewer", name="user_role")
    user_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM("admin", "analyst", "viewer", name="user_role", create_type=False),
            nullable=False,
            server_default=sa.text("'analyst'::user_role"),
        ),
    )
    op.execute(
        "UPDATE users SET role = 'admin'::user_role "
        "WHERE platform_role = 'platform_admin'::platform_role"
    )
    op.drop_column("users", "platform_role")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "avatar_url")
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=150),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column("users", "password_hash", new_column_name="hashed_password")

    op.drop_index("ix_project_integrations_project_id", table_name="project_integrations")
    op.drop_table("project_integrations")

    op.drop_index("ix_projects_created_by", table_name="projects")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_organization_members_user_id", table_name="organization_members")
    op.drop_index("ix_organization_members_organization_id", table_name="organization_members")
    op.drop_table("organization_members")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")

    _drop_new_enums()
