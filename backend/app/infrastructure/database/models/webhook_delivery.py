"""Idempotent inbound webhook delivery ledger (ADR-005).

Stores a sanitised event snapshot only — never the raw unredacted payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, UUIDPrimaryKeyMixin


class WebhookDelivery(Base, UUIDPrimaryKeyMixin):
    """One inbound webhook delivery and its durable processing state."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_webhook_deliveries_provider_id"),
        Index("ix_webhook_deliveries_repository_id_received_at", "repository_id", "received_at"),
        Index("ix_webhook_deliveries_processing_status", "processing_status"),
    )

    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="github")
    delivery_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_name: Mapped[str] = mapped_column(String(80), nullable=False)
    event_action: Mapped[str | None] = mapped_column(String(80), nullable=True)
    installation_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitised_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
