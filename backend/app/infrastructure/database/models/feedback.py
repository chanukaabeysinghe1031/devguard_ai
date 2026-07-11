"""User feedback on recommendations."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.recommendation import Recommendation
    from app.infrastructure.database.models.user import User


class Feedback(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_feedback_rating_range",
        ),
        Index("ix_feedback_user_id", "user_id"),
        Index("ix_feedback_pipeline_run_id", "pipeline_run_id"),
        Index("ix_feedback_recommendation_id", "recommendation_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_helpful: Mapped[bool | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="feedback_items")
    pipeline_run: Mapped[PipelineRun] = relationship(back_populates="feedback_items")
    recommendation: Mapped[Recommendation | None] = relationship(back_populates="feedback_items")
