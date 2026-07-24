"""Structured resolution information for an incident."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.user import User


class IncidentResolution(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One active resolution record normally exists per resolved incident;
    reopened incidents may receive additional resolution records."""

    __tablename__ = "incident_resolutions"
    __table_args__ = (Index("ix_incident_resolutions_incident_id", "incident_id"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    resolved_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    resolution_summary: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_steps: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    prevention_actions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    time_spent_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_recommendation_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    incident: Mapped[Incident] = relationship(back_populates="resolutions")
    resolver: Mapped[User] = relationship(back_populates="incident_resolutions")
