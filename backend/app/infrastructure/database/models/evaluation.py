"""Formal MSc and operational model evaluation results."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.model_version import ModelVersion


class Evaluation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "evaluations"
    __table_args__ = (Index("ix_evaluations_model_version_id", "model_version_id"),)

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    dataset_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evaluation_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    model_version: Mapped[ModelVersion] = relationship(back_populates="evaluations")
