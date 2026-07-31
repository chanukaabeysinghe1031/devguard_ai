"""User notification related to incidents and analyses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import DeliveryStatus, NotificationType
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import delivery_status_enum, notification_type_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.user import User


class Notification(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "ix_notifications_organization_id_user_id_created_at",
            "organization_id",
            "user_id",
            "created_at",
        ),
        Index("ix_notifications_user_id_is_read_created_at", "user_id", "is_read", "created_at"),
        Index("ix_notifications_incident_id", "incident_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        notification_type_enum,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        delivery_status_enum,
        nullable=False,
        default=DeliveryStatus.PENDING,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="notifications")
    incident: Mapped[Incident | None] = relationship(back_populates="notifications")
