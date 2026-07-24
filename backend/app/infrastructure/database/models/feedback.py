"""User evaluation of AI output (classification, evidence, recommendation, overall)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.prediction import Prediction
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
        Index("ix_feedback_incident_id", "incident_id"),
        Index("ix_feedback_analysis_run_id", "analysis_run_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(40), nullable=False)
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="feedback_items")
    incident: Mapped[Incident] = relationship(back_populates="feedback_items")
    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="feedback_items")
    prediction: Mapped[Prediction | None] = relationship(back_populates="feedback_items")
    recommendation: Mapped[Recommendation | None] = relationship(back_populates="feedback_items")
