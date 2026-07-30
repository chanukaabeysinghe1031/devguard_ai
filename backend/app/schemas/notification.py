"""Notification API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import PaginatedResponse


class NotificationResponse(BaseModel):
    id: UUID
    notification_type: str
    title: str
    message: str
    severity: str | None = None
    channel: str
    delivery_status: str
    is_read: bool
    incident_id: UUID | None = None
    created_at: datetime
    read_at: datetime | None = None


class NotificationListResponse(PaginatedResponse[NotificationResponse]):
    unread_count: int = 0
