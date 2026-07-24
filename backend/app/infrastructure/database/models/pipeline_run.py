"""CI/CD pipeline execution model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CiProvider, PipelineRunStatus
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import ci_provider_enum, pipeline_run_status_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.uploaded_file import UploadedFile


class PipelineRun(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """One CI/CD workflow, deployment, or infrastructure execution.

    Owned by a project — pipeline runs have no direct user ownership.
    """

    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_project_id_created_at", "project_id", "created_at"),
        Index("ix_pipeline_runs_project_id_status", "project_id", "status"),
        Index("ix_pipeline_runs_provider_external_run_id", "provider", "external_run_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[CiProvider] = mapped_column(ci_provider_enum, nullable=False)
    workflow_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(100), nullable=True)
    triggered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[PipelineRunStatus] = mapped_column(
        pipeline_run_status_enum,
        nullable=False,
        default=PipelineRunStatus.QUEUED,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    project: Mapped[Project] = relationship(back_populates="pipeline_runs")
    incidents: Mapped[list[Incident]] = relationship(back_populates="pipeline_run")
    uploaded_files: Mapped[list[UploadedFile]] = relationship(back_populates="pipeline_run")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="pipeline_run")
