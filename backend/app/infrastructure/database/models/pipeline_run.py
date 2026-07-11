"""Pipeline analysis run model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import PipelineRunStatus
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import pipeline_run_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_history import AnalysisHistory
    from app.infrastructure.database.models.evidence_item import EvidenceItem
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.prediction import Prediction
    from app.infrastructure.database.models.recommendation import Recommendation
    from app.infrastructure.database.models.uploaded_file import UploadedFile
    from app.infrastructure.database.models.user import User


class PipelineRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_user_id_status_created_at", "user_id", "status", "created_at"),
        Index("ix_pipeline_runs_uploaded_file_id", "uploaded_file_id"),
        Index("ix_pipeline_runs_workflow_file_id", "workflow_file_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[PipelineRunStatus] = mapped_column(
        pipeline_run_status_enum,
        nullable=False,
        default=PipelineRunStatus.PENDING,
    )
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_log_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    user: Mapped[User] = relationship(back_populates="pipeline_runs")
    uploaded_file: Mapped[UploadedFile] = relationship(
        back_populates="pipeline_runs_as_log",
        foreign_keys=[uploaded_file_id],
    )
    workflow_file: Mapped[UploadedFile | None] = relationship(
        back_populates="pipeline_runs_as_workflow",
        foreign_keys=[workflow_file_id],
    )
    predictions: Mapped[list[Prediction]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    evidence_items: Mapped[list[EvidenceItem]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    recommendations: Mapped[list[Recommendation]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list[Feedback]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
    history_entries: Mapped[list[AnalysisHistory]] = relationship(
        back_populates="pipeline_run",
        cascade="all, delete-orphan",
    )
