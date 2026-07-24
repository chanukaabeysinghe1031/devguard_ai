"""AI analysis run model — one execution of the full AI pipeline for an incident."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AnalysisRunStatus
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import analysis_run_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.evidence_item import EvidenceItem
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.prediction import Prediction
    from app.infrastructure.database.models.recommendation import Recommendation
    from app.infrastructure.database.models.recommendation_step import RecommendationStep
    from app.infrastructure.database.models.retrieved_document import RetrievedDocument
    from app.infrastructure.database.models.user import User


class AnalysisRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One execution of the complete AI pipeline. An incident may be analyzed
    multiple times, and each run is independently traceable."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_incident_id_created_at", "incident_id", "created_at"),
        Index("ix_analysis_runs_status_created_at", "status", "created_at"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AnalysisRunStatus] = mapped_column(
        analysis_run_status_enum,
        nullable=False,
        default=AnalysisRunStatus.QUEUED,
    )
    analysis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_stage: Mapped[str | None] = mapped_column(String(60), nullable=True)
    progress_percentage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    incident: Mapped[Incident] = relationship(
        back_populates="analysis_runs",
        foreign_keys=[incident_id],
    )
    pipeline_run: Mapped[PipelineRun | None] = relationship(back_populates="analysis_runs")
    requester: Mapped[User | None] = relationship()
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    recommendation_steps: Mapped[list[RecommendationStep]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    retrieved_documents: Mapped[list[RetrievedDocument]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list[Feedback]] = relationship(back_populates="analysis_run")
