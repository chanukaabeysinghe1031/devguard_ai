"""Generated incident report metadata."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import GenerationStatus
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import generation_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.user import User


class IncidentReport(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "incident_reports"
    __table_args__ = (Index("ix_incident_reports_incident_id", "incident_id"),)

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_status: Mapped[GenerationStatus] = mapped_column(
        generation_status_enum,
        nullable=False,
        default=GenerationStatus.PENDING,
    )

    incident: Mapped[Incident] = relationship(back_populates="reports")
    generator: Mapped[User | None] = relationship(back_populates="incident_reports")
