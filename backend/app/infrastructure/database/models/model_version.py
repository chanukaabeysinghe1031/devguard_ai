"""ML model version registry."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.evaluation import Evaluation
    from app.infrastructure.database.models.prediction import Prediction


class ModelVersion(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_versions_name_version"),
        Index("ix_model_versions_name", "name"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    classifier_type: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    training_dataset_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="model_version")
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="model_version",
        cascade="all, delete-orphan",
    )
