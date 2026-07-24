"""Recommendation parent/summary model for AI remediation guidance."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.prediction import Prediction
    from app.infrastructure.database.models.recommendation_step import RecommendationStep


class Recommendation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    """Parent/summary record for AI remediation guidance produced by an analysis run.

    Ordered steps are NOT stored as columns here — they live in
    ``recommendation_steps``. ``legacy_remediation_steps`` is retained only for
    backward-compatibility with pre-Migration-004 data and is deprecated; it is
    never the source of truth.
    """

    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_recommendations_confidence_score_range",
        ),
        Index("ix_recommendations_analysis_run_id", "analysis_run_id"),
        Index("ix_recommendations_prediction_id", "prediction_id"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    legacy_remediation_steps: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Deprecated pre-Migration-004 JSON blob; recommendation_steps is authoritative.",
    )

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="recommendations")
    prediction: Mapped[Prediction | None] = relationship(back_populates="recommendations")
    steps: Mapped[list[RecommendationStep]] = relationship(
        back_populates="recommendation",
        cascade="all, delete-orphan",
        order_by="RecommendationStep.step_number",
        lazy="selectin",
    )
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="recommendation")
