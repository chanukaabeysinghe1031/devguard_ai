"""Organization access grant for a shared GitHub App installation (ADR-005).

A single GitHub App installation (``github_installations``) is a global
identity — it may be granted access by, and used from, multiple DevGuard
organizations. Each row here is one organization's independent access grant;
it is never treated as exclusive ownership of the underlying installation.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
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
    from app.infrastructure.database.models.organization import Organization
    from app.infrastructure.database.models.user import User


class GitHubInstallationOrganizationAccess(
    Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin
):
    """One organization's access grant to a shared GitHub App installation."""

    __tablename__ = "github_installation_organization_access"
    __table_args__ = (
        UniqueConstraint(
            "installation_id",
            "organization_id",
            name="uq_github_install_org_access",
        ),
        Index("ix_github_install_org_access_organization_id", "organization_id"),
        Index("ix_github_install_org_access_installation_id", "installation_id"),
        Index("ix_github_install_org_access_status", "status"),
    )

    installation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_installations.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    linked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disconnected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    permissions_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    repository_selection: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_repository_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    installation: Mapped[GitHubInstallation] = relationship(
        back_populates="organization_accesses"
    )
    organization: Mapped[Organization] = relationship()
    linked_by_user: Mapped[User | None] = relationship()
