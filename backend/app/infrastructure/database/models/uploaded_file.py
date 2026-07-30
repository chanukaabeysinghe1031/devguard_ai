"""Uploaded file metadata model (logs, configuration, archives)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import (
    FileProcessingStatus,
    FileType,
    FileValidationStatus,
    SecretMaskingStatus,
)
from app.infrastructure.database.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.enums import (
    file_processing_status_enum,
    file_type_enum,
    file_validation_status_enum,
    secret_masking_status_enum,
)

if TYPE_CHECKING:
    from app.infrastructure.database.models.evidence_item import EvidenceItem
    from app.infrastructure.database.models.incident import Incident
    from app.infrastructure.database.models.pipeline_run import PipelineRun
    from app.infrastructure.database.models.project import Project
    from app.infrastructure.database.models.user import User


class UploadedFile(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Metadata for logs, configuration files, and archives submitted for analysis.

    ``created_at`` (via ``CreatedAtMixin``) is the upload timestamp; no separate
    ``uploaded_at`` column is stored. Large raw content lives outside PostgreSQL.
    """

    __tablename__ = "uploaded_files"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="ck_uploaded_files_size_bytes_non_negative"),
        Index("ix_uploaded_files_project_id", "project_id"),
        Index("ix_uploaded_files_incident_id", "incident_id"),
        Index("ix_uploaded_files_pipeline_run_id", "pipeline_run_id"),
    )

    # Nullable for system ingestion (e.g. GitHub Actions logs) with no human uploader.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_type: Mapped[FileType] = mapped_column(file_type_enum, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(150), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_masking_status: Mapped[SecretMaskingStatus] = mapped_column(
        secret_masking_status_enum,
        nullable=False,
        default=SecretMaskingStatus.PENDING,
    )
    validation_status: Mapped[FileValidationStatus] = mapped_column(
        file_validation_status_enum,
        nullable=False,
        default=FileValidationStatus.PENDING,
    )
    processing_status: Mapped[FileProcessingStatus] = mapped_column(
        file_processing_status_enum,
        nullable=False,
        default=FileProcessingStatus.PENDING,
    )
    extracted_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="uploaded_files")
    project: Mapped[Project] = relationship(back_populates="uploaded_files")
    pipeline_run: Mapped[PipelineRun | None] = relationship(back_populates="uploaded_files")
    incident: Mapped[Incident | None] = relationship(back_populates="uploaded_files")
    evidence_items: Mapped[list[EvidenceItem]] = relationship(back_populates="uploaded_file")
