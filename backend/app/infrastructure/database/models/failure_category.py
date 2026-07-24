"""Failure category taxonomy model (normalized, restricted-delete)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import IncidentSeverity
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import incident_severity_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.prediction import Prediction


class FailureCategory(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Normalized failure taxonomy. Restricted delete — categories are referenced by predictions."""

    __tablename__ = "failure_categories"
    __table_args__ = (Index("ix_failure_categories_code", "code"),)

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("failure_categories.id", ondelete="RESTRICT"),
        nullable=True,
    )
    default_severity: Mapped[IncidentSeverity | None] = mapped_column(
        incident_severity_enum,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parent: Mapped[FailureCategory | None] = relationship(
        back_populates="children",
        remote_side="FailureCategory.id",
    )
    children: Mapped[list[FailureCategory]] = relationship(back_populates="parent")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="failure_category")
