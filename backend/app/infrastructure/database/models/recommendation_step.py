"""Normalized ordered remediation/verification/prevention step for a recommendation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import RecommendationStepType, RiskLevel
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import recommendation_step_type_enum, risk_level_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_run import AnalysisRun
    from app.infrastructure.database.models.recommendation import Recommendation


class RecommendationStep(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Durable source of truth for ordered recommendation guidance.

    ``analysis_run_id`` is denormalized from the parent recommendation for
    analysis-scoped query convenience.
    """

    __tablename__ = "recommendation_steps"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id", "step_number", name="uq_recommendation_steps_recommendation_step"
        ),
    )

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[RecommendationStepType] = mapped_column(
        recommendation_step_type_enum,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[RiskLevel | None] = mapped_column(risk_level_enum, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    command_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    recommendation: Mapped[Recommendation] = relationship(back_populates="steps")
    analysis_run: Mapped[AnalysisRun] = relationship(back_populates="recommendation_steps")
