"""Incident assignment history record."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.user import User


class IncidentAssignment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "incident_assignments"
    __table_args__ = (Index("ix_incident_assignments_incident_id", "incident_id"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="assignments")
    assignee: Mapped[User] = relationship(
        back_populates="assignments_received",
        foreign_keys=[assigned_to],
    )
    assigner: Mapped[User | None] = relationship(
        back_populates="assignments_made",
        foreign_keys=[assigned_by],
    )
