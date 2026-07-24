"""Failure classification / root-cause prediction model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.evidence_item import EvidenceItem
    from app.infrastructure.database.models.failure_category import FailureCategory
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.model_version import ModelVersion
    from app.infrastructure.database.models.recommendation import Recommendation


class Prediction(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Structured classification and root-cause prediction result for an analysis run."""

    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_predictions_confidence_range",
        ),
        UniqueConstraint("analysis_run_id", "rank", name="uq_predictions_analysis_run_rank"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    failure_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("failure_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    rank: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    predicted_label: Mapped[str] = mapped_column(String(150), nullable=False)
    root_cause_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    technical_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="predictions")
    failure_category: Mapped[FailureCategory] = relationship(back_populates="predictions")
    model_version: Mapped[ModelVersion] = relationship(back_populates="predictions")
    evidence_items: Mapped[list[EvidenceItem]] = relationship(back_populates="prediction")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="prediction")
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="prediction")
