"""Incident model — the central operational object in DevGuard AI."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import IncidentPriority, IncidentSeverity, IncidentStatus
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import (
    incident_priority_enum,
    incident_severity_enum,
    incident_status_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.incident_assignment import IncidentAssignment
    from app.infrastructure.database.models.incident_event import IncidentEvent
    from app.infrastructure.database.models.incident_note import IncidentNote
    from app.infrastructure.database.models.incident_report import IncidentReport
    from app.infrastructure.database.models.incident_resolution import IncidentResolution
    from app.infrastructure.database.models.notification import Notification
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.uploaded_file import UploadedFile
    from app.infrastructure.database.models.user import User

incident_number_seq = Sequence("incident_number_seq")


class Incident(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Central operational entity: created from a pipeline failure, manual upload,
    or an integration-detected deployment problem."""

    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_project_id_created_at", "project_id", "created_at"),
        Index("ix_incidents_project_id_status", "project_id", "status"),
        Index("ix_incidents_severity_status", "severity", "status"),
        Index("ix_incidents_current_assignee_id_status", "current_assignee_id", "status"),
        Index("ix_incidents_detected_at", "detected_at"),
    )

    incident_number: Mapped[int] = mapped_column(
        BigInteger,
        incident_number_seq,
        unique=True,
        nullable=False,
        server_default=incident_number_seq.next_value(),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(
        incident_status_enum,
        nullable=False,
        default=IncidentStatus.DETECTED,
    )
    severity: Mapped[IncidentSeverity] = mapped_column(incident_severity_enum, nullable=False)
    priority: Mapped[IncidentPriority | None] = mapped_column(
        incident_priority_enum,
        nullable=True,
    )
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    latest_analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    project: Mapped[Project] = relationship(back_populates="incidents")
    pipeline_run: Mapped[PipelineRun | None] = relationship(back_populates="incidents")
    creator: Mapped[User | None] = relationship(
        back_populates="created_incidents",
        foreign_keys=[created_by],
    )
    current_assignee: Mapped[User | None] = relationship(
        back_populates="assigned_incidents",
        foreign_keys=[current_assignee_id],
    )
    latest_analysis_run: Mapped[AnalysisRun | None] = relationship(
        foreign_keys=[latest_analysis_run_id],
        post_update=True,
    )
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        foreign_keys="AnalysisRun.incident_id",
    )
    uploaded_files: Mapped[list[UploadedFile]] = relationship(back_populates="incident")
    events: Mapped[list[IncidentEvent]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentEvent.occurred_at",
    )
    notes: Mapped[list[IncidentNote]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[IncidentAssignment]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    resolutions: Mapped[list[IncidentResolution]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list[IncidentReport]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list[Notification]] = relationship(back_populates="incident")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="incident")
