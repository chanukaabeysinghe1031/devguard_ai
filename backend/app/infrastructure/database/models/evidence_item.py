"""Extracted evidence item model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EvidenceType
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import evidence_type_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.prediction import Prediction


class EvidenceItem(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evidence_items"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 1",
            name="ck_evidence_items_relevance_score_range",
        ),
        Index("ix_evidence_items_pipeline_run_id", "pipeline_run_id"),
        Index("ix_evidence_items_prediction_id", "prediction_id"),
    )

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(evidence_type_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    highlight_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    highlight_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="evidence_items")
    prediction: Mapped[Prediction | None] = relationship(back_populates="evidence_items")
