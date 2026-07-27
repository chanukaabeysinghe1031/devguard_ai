"""File upload API schemas. Never expose storage paths."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UploadedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    file_type: str
    size_bytes: int
    checksum_sha256: str
    validation_status: str
    secret_masking_status: str
    processing_status: str
    uploaded_at: datetime | None = None
    mime_type: str | None = None
    incident_id: UUID | None = None
    project_id: UUID | None = None
    pipeline_run_id: UUID | None = None


class UploadFilesResponse(BaseModel):
    files: list[UploadedFileResponse]


class FileDetailResponse(UploadedFileResponse):
    extracted_metadata: dict | None = None


class FileListResponse(BaseModel):
    items: list[UploadedFileResponse] = Field(default_factory=list)
