"""Failure category taxonomy model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.infrastructure.database.models.prediction import Prediction


class FailureCategory(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "failure_categories"
    __table_args__ = (Index("ix_failure_categories_slug", "slug"),)

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="category")
