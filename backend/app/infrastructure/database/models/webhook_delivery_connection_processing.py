"""Per-connection fan-out processing outcome for a webhook delivery (ADR-005).

A single inbound webhook delivery (``webhook_deliveries``) may match
repository connections belonging to multiple DevGuard organizations when the
underlying GitHub App installation is shared. Each row here tracks the
independent processing outcome for one matching connection so that one
tenant's failure or success can never be conflated with another's.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.organization import Organization
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.webhook_delivery import WebhookDelivery


class WebhookDeliveryConnectionProcessing(
    Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin
):
    """One repository connection's independent processing outcome for a delivery."""

    __tablename__ = "webhook_delivery_connection_processing"
    __table_args__ = (
        UniqueConstraint(
            "webhook_delivery_id",
            "repository_connection_id",
            name="uq_webhook_delivery_connection",
        ),
        Index("ix_webhook_delivery_conn_processing_organization_id", "organization_id"),
        Index(
            "ix_webhook_delivery_conn_processing_repo_connection_id",
            "repository_connection_id",
        ),
        Index("ix_webhook_delivery_conn_processing_status", "status"),
    )

    webhook_delivery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_deliveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    repository_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("github_repository_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    webhook_delivery: Mapped[WebhookDelivery] = relationship()
    repository_connection: Mapped[GitHubRepositoryConnection] = relationship()
    organization: Mapped[Organization] = relationship()
    project: Mapped[Project] = relationship()
    pipeline_run: Mapped[PipelineRun | None] = relationship()
    incident: Mapped[Incident | None] = relationship()
