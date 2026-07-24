"""Supporting evidence extracted from uploaded files and logs."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import EvidenceType
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import evidence_type_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.prediction import Prediction
    from app.infrastructure.database.models.uploaded_file import UploadedFile


class EvidenceItem(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Supporting evidence extracted from uploaded files and logs.

    Security requirement: only masked and sanitized excerpts should be stored.
    """

    __tablename__ = "evidence_items"
    __table_args__ = (
        Index("ix_evidence_items_analysis_run_id", "analysis_run_id"),
        Index("ix_evidence_items_prediction_id", "prediction_id"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(evidence_type_enum, nullable=False)
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="evidence_items")
    prediction: Mapped[Prediction | None] = relationship(back_populates="evidence_items")
    uploaded_file: Mapped[UploadedFile | None] = relationship(back_populates="evidence_items")
