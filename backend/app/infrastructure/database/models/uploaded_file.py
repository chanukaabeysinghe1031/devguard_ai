"""Uploaded file metadata model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import FileType
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import file_type_enum

if TYPE_CHECKING:
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.user import User


class UploadedFile(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "uploaded_files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_non_negative"),
        Index("ix_uploaded_files_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[FileType] = mapped_column(file_type_enum, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    platform: Mapped[str] = mapped_column(String(64), nullable=False)
    is_processed: Mapped[bool] = mapped_column(nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="uploaded_files")
    pipeline_runs_as_log: Mapped[list[PipelineRun]] = relationship(
        back_populates="uploaded_file",
        foreign_keys="PipelineRun.uploaded_file_id",
    )
    pipeline_runs_as_workflow: Mapped[list[PipelineRun]] = relationship(
        back_populates="workflow_file",
        foreign_keys="PipelineRun.workflow_file_id",
    )
