"""Global GitHub App installation identity (ADR-005).

A row here represents one GitHub App installation on a GitHub account/org —
it is a global identity, not the exclusive property of one DevGuard
organization. Which DevGuard organizations may use it is recorded in
``github_installation_organization_access``; ``organization_id`` on this
table is retained only as legacy/original-linker metadata and must not be
used as an authorization check.

No installation access tokens are ever persisted here — tokens are minted on
demand and held in memory only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.github_installation_organization_access import (
        GitHubInstallationOrganizationAccess,
    )
    from app.infrastructure.database.models.github_repository_connection import (
        GitHubRepositoryConnection,
    )
    from app.infrastructure.database.models.organization import Organization


class GitHubInstallation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """A global GitHub App installation identity (not exclusive org ownership).

    Organization access is granted/revoked independently via
    ``organization_accesses``; this row's ``organization_id`` is legacy
    metadata (the original linker) only.
    """

    __tablename__ = "github_installations"
    __table_args__ = (
        UniqueConstraint(
            "github_installation_id",
            name="uq_github_installations_github_installation_id",
        ),
        Index("ix_github_installations_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    github_installation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    github_account_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    github_account_login: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    permissions_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    repository_selection: Mapped[str | None] = mapped_column(String(40), nullable=True)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization | None] = relationship()
    connections: Mapped[list[GitHubRepositoryConnection]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan",
    )
    organization_accesses: Mapped[list[GitHubInstallationOrganizationAccess]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan",
    )
