"""Repository → project connection with ingestion automation flags (ADR-005)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.github_installation import GitHubInstallation
    from app.infrastructure.database.models.github_installation_organization_access import (
        GitHubInstallationOrganizationAccess,
    )
    from app.infrastructure.database.models.project import Project


class GitHubRepositoryConnection(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Maps one GitHub repository to one DevGuard project.

    Partial unique indexes (see migration 009) allow only one live connection
    per repository within an organization and one live connection per project.
    ``installation_access_id`` records which organization access grant this
    connection was created under (shared-installation support, migration 019).
    """

    __tablename__ = "github_repository_connections"
    __table_args__ = (
        Index("ix_github_repository_connections_github_repository_id", "github_repository_id"),
        Index("ix_github_repository_connections_project_id", "project_id"),
        Index("ix_github_repository_connections_installation_id", "github_installation_id"),
        Index(
            "ix_github_repository_connections_installation_access_id",
            "installation_access_id",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    github_installation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_installations.id", ondelete="CASCADE"),
        nullable=False,
    )
    installation_access_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("github_installation_organization_access.id", ondelete="SET NULL"),
        nullable=True,
    )
    github_repository_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    repository_full_name: Mapped[str] = mapped_column(String(500), nullable=False)
    repository_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_create_incidents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_start_analysis: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_on_failure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    workflow_filters_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    branch_filters_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    failure_conclusions_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    environment_mapping_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    severity_rules_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_webhook_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    installation: Mapped[GitHubInstallation] = relationship(back_populates="connections")
    installation_access: Mapped[GitHubInstallationOrganizationAccess | None] = relationship()
    project: Mapped[Project] = relationship()
