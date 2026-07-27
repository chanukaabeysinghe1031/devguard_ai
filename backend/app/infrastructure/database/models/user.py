"""User account model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import PlatformRole
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import platform_role_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.audit_log import AuditLog
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.incident_assignment import IncidentAssignment
    from app.infrastructure.database.models.incident_event import IncidentEvent
    from app.infrastructure.database.models.incident_note import IncidentNote
    from app.infrastructure.database.models.incident_report import IncidentReport
    from app.infrastructure.database.models.incident_resolution import IncidentResolution
    from app.infrastructure.database.models.notification import Notification
    from app.infrastructure.database.models.organization_member import OrganizationMember
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.refresh_token import RefreshToken
    from app.infrastructure.database.models.uploaded_file import UploadedFile


class User(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Authenticated platform user."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform_role: Mapped[PlatformRole] = mapped_column(
        platform_role_enum,
        nullable=False,
        default=PlatformRole.NONE,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization_memberships: Mapped[list[OrganizationMember]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    created_projects: Mapped[list[Project]] = relationship(back_populates="creator")
    uploaded_files: Mapped[list[UploadedFile]] = relationship(back_populates="user")
    created_incidents: Mapped[list[Incident]] = relationship(
        back_populates="creator",
        foreign_keys="Incident.created_by",
    )
    assigned_incidents: Mapped[list[Incident]] = relationship(
        back_populates="current_assignee",
        foreign_keys="Incident.current_assignee_id",
    )
    incident_events: Mapped[list[IncidentEvent]] = relationship(back_populates="actor_user")
    incident_notes: Mapped[list[IncidentNote]] = relationship(back_populates="author")
    assignments_received: Mapped[list[IncidentAssignment]] = relationship(
        back_populates="assignee",
        foreign_keys="IncidentAssignment.assigned_to",
    )
    assignments_made: Mapped[list[IncidentAssignment]] = relationship(
        back_populates="assigner",
        foreign_keys="IncidentAssignment.assigned_by",
    )
    incident_resolutions: Mapped[list[IncidentResolution]] = relationship(
        back_populates="resolver",
    )
    incident_reports: Mapped[list[IncidentReport]] = relationship(back_populates="generator")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list[Feedback]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
