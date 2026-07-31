"""Organization (tenant/workspace) model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import OrganizationStatus
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import organization_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.audit_log import AuditLog
    from app.infrastructure.database.models.organization_invitation import (
        OrganizationInvitation,
    )
    from app.infrastructure.database.models.organization_member import OrganizationMember
    from app.infrastructure.database.models.project import Project


class Organization(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """A company, team, or workspace using DevGuard AI."""

    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="mvp")
    status: Mapped[OrganizationStatus] = mapped_column(
        organization_status_enum,
        nullable=False,
        default=OrganizationStatus.ACTIVE,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    invitations: Mapped[list[OrganizationInvitation]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list[Project]] = relationship(back_populates="organization")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="organization")
