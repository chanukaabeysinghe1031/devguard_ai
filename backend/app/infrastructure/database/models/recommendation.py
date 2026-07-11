"""LLM-generated recommendation model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import RiskLevel
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import risk_level_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.prediction import Prediction


class Recommendation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_recommendations_confidence_score_range",
        ),
        Index("ix_recommendations_pipeline_run_id", "pipeline_run_id"),
        Index("ix_recommendations_prediction_id", "prediction_id"),
    )

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    remediation_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        risk_level_enum,
        nullable=False,
        default=RiskLevel.MEDIUM,
    )
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    preventive_actions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    future_improvements: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False)
    rag_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="recommendations")
    prediction: Mapped[Prediction | None] = relationship(back_populates="recommendations")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="recommendation")
