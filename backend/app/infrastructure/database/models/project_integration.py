"""External integration metadata model (no raw secrets)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import IntegrationStatus
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import integration_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.project import Project


class ProjectIntegration(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """External integration metadata for a project (e.g. GitHub, Slack).

    Security rule: raw access tokens/secrets must never be stored here. Only a
    reference to a secret manager entry may be persisted.
    """

    __tablename__ = "project_integrations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(60), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    encrypted_secret_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IntegrationStatus] = mapped_column(
        integration_status_enum,
        nullable=False,
        default=IntegrationStatus.ACTIVE,
    )

    project: Mapped[Project] = relationship(back_populates="integrations")
