"""Organization-scoped GitHub App installation metadata (ADR-005).

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
    from app.infrastructure.database.models.github_repository_connection import (
        GitHubRepositoryConnection,
    )
    from app.infrastructure.database.models.organization import Organization


class GitHubInstallation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """A GitHub App installation bound to a DevGuard organization."""

    __tablename__ = "github_installations"
    __table_args__ = (
        UniqueConstraint(
            "github_installation_id",
            name="uq_github_installations_github_installation_id",
        ),
        Index("ix_github_installations_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
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

    organization: Mapped[Organization] = relationship()
    connections: Mapped[list[GitHubRepositoryConnection]] = relationship(
        back_populates="installation",
        cascade="all, delete-orphan",
    )
