"""Model evaluation results."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.model_version import ModelVersion
    from app.infrastructure.database.models.user import User


class Evaluation(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_evaluations_model_version_id", "model_version_id"),
        Index("ix_evaluations_user_id", "user_id"),
    )

    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    model_version: Mapped[ModelVersion] = relationship(back_populates="evaluations")
    user: Mapped[User | None] = relationship(back_populates="evaluations")
