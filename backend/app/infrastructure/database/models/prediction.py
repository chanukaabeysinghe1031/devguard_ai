"""Failure classification prediction model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.evidence_item import EvidenceItem
    from app.infrastructure.database.models.failure_category import FailureCategory
    from app.infrastructure.database.models.model_version import ModelVersion
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.recommendation import Recommendation


class Prediction(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_predictions_confidence_score_range",
        ),
        Index("ix_predictions_pipeline_run_id", "pipeline_run_id"),
        Index("ix_predictions_category_id", "category_id"),
        Index("ix_predictions_model_version_id", "model_version_id"),
    )

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    classifier_name: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_vector_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    probabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="predictions")
    category: Mapped[FailureCategory] = relationship(back_populates="predictions")
    model_version: Mapped[ModelVersion | None] = relationship(back_populates="predictions")
    evidence_items: Mapped[list[EvidenceItem]] = relationship(back_populates="prediction")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="prediction")
