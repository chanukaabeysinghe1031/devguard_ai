"""User account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import UserRole
from app.infrastructure.database.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPrimaryKeyMixin,
)
from app.infrastructure.database.enums import user_role_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.analysis_history import AnalysisHistory
    from app.infrastructure.database.models.evaluation import Evaluation
    from app.infrastructure.database.models.feedback import Feedback
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.uploaded_file import UploadedFile


class User(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum,
        nullable=False,
        default=UserRole.ANALYST,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    uploaded_files: Mapped[list[UploadedFile]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    pipeline_runs: Mapped[list[PipelineRun]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback_items: Mapped[list[Feedback]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    history_entries: Mapped[list[AnalysisHistory]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list[Evaluation]] = relationship(back_populates="user")
