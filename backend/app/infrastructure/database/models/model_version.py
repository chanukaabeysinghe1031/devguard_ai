"""Reproducible ML model version registry."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import ModelVersionStatus
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import model_version_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.evaluation import Evaluation
    from app.infrastructure.database.models.prediction import Prediction


class ModelVersion(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_versions_model_name_version"),
        Index("ix_model_versions_model_name", "model_name"),
    )

    model_name: Mapped[str] = mapped_column(String(150), nullable=False)
    model_type: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    training_dataset_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    configuration: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ModelVersionStatus] = mapped_column(
        model_version_status_enum,
        nullable=False,
        default=ModelVersionStatus.TRAINING,
    )
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="model_version")
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="model_version",
        cascade="all, delete-orphan",
    )
