"""Analysis activity audit history."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.user import User


class AnalysisHistory(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "analysis_history"
    __table_args__ = (
        Index("ix_analysis_history_user_id_created_at", "user_id", "created_at"),
        Index("ix_analysis_history_pipeline_run_id", "pipeline_run_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    user: Mapped[User] = relationship(back_populates="history_entries")
    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="history_entries")
