"""Secure file upload application service."""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.domain.enums import (
    AnalysisRunStatus,
    FileProcessingStatus,
    FileValidationStatus,
    SecretMaskingStatus,
)
from app.domain.exceptions.business import ResourceNotFoundError, ValidationBusinessError
from app.domain.exceptions.upload import (
    DuplicateFileError,
    FileDeletionForbiddenError,
    FileTooLargeError,
    TooManyFilesError,
    UnsupportedFileTypeError,
)
from app.domain.interfaces.storage_provider import FileStorage
from app.domain.services.file_validation import (
    decode_text_content,
    detect_file_type,
    ensure_non_empty,
    sanitize_original_filename,
)
from app.domain.services.secret_masker import mask_secrets
from app.infrastructure.database.models.analysis_run import AnalysisRun
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.incident_event import IncidentEvent
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.uploaded_file import UploadedFile
from app.infrastructure.parsers.metadata_extractors import get_parser_for, validate_syntax
from app.schemas.file import (
    FileDetailResponse,
    FileListResponse,
    UploadedFileResponse,
    UploadFilesResponse,
)

logger = structlog.get_logger(__name__)


class UploadService:
    """Validates, masks, stores, and tracks uploaded incident artifacts."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        storage: FileStorage,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage

    async def upload_incident_files(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        uploader_id: UUID,
        files: list[tuple[str | None, bytes]],
        file_category: str | None = None,
        description: str | None = None,
    ) -> UploadFilesResponse:
        if not files:
            raise ValidationBusinessError("At least one file is required.", error_code="EMPTY_FILE")
        if len(files) > self._settings.max_files_per_upload:
            raise TooManyFilesError()

        incident = await self._load_incident(organization_id, incident_id)
        saved: list[UploadedFile] = []
        storage_keys: list[str] = []

        try:
            for original_name, raw in files:
                record, key = await self._process_one(
                    incident=incident,
                    uploader_id=uploader_id,
                    original_name=original_name,
                    raw=raw,
                    file_category=file_category,
                    description=description,
                )
                saved.append(record)
                storage_keys.append(key)

            await self._session.flush()
            await self._record_event(
                incident_id=incident.id,
                actor_id=uploader_id,
                title="Files uploaded",
                description=f"{len(saved)} file(s) uploaded.",
                metadata={"file_ids": [str(f.id) for f in saved]},
            )
            await self._session.flush()
        except Exception:
            for key in storage_keys:
                try:
                    await self._storage.delete(relative_path=key)
                except Exception:
                    logger.warning("partial_upload_cleanup_failed", storage_key=key)
            raise

        logger.info(
            "files_uploaded",
            incident_id=str(incident_id),
            file_count=len(saved),
        )
        return UploadFilesResponse(files=[self._to_response(f) for f in saved])

    async def list_incident_files(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
    ) -> FileListResponse:
        await self._load_incident(organization_id, incident_id)
        stmt = (
            select(UploadedFile)
            .where(UploadedFile.incident_id == incident_id)
            .order_by(UploadedFile.created_at.desc())
        )
        files = list((await self._session.scalars(stmt)).all())
        return FileListResponse(items=[self._to_response(f) for f in files])

    async def get_file(
        self,
        *,
        organization_id: UUID,
        file_id: UUID,
    ) -> FileDetailResponse:
        uploaded = await self._load_file_in_org(organization_id, file_id)
        base = self._to_response(uploaded)
        return FileDetailResponse(
            **base.model_dump(),
            extracted_metadata=uploaded.extracted_metadata,
        )

    async def delete_file(
        self,
        *,
        organization_id: UUID,
        file_id: UUID,
        actor_id: UUID,
    ) -> None:
        uploaded = await self._load_file_in_org(organization_id, file_id)
        await self._assert_deletable(uploaded)
        storage_key = uploaded.storage_path
        incident_id = uploaded.incident_id
        await self._session.delete(uploaded)
        await self._session.flush()
        await self._storage.delete(relative_path=storage_key)
        if incident_id is not None:
            await self._record_event(
                incident_id=incident_id,
                actor_id=actor_id,
                title="File deleted",
                description=f"Deleted file {uploaded.original_filename}",
                metadata={"file_id": str(file_id)},
            )
            await self._session.flush()
        logger.info("file_deleted", file_id=str(file_id))

    async def validate_files_for_analysis(
        self,
        *,
        organization_id: UUID,
        incident_id: UUID,
        file_ids: list[UUID],
    ) -> list[UploadedFile]:
        """Ensure file_ids belong to the incident, org, and are valid for analysis."""
        await self._load_incident(organization_id, incident_id)
        if not file_ids:
            return []

        unique_ids = list(dict.fromkeys(file_ids))
        stmt = select(UploadedFile).where(
            UploadedFile.id.in_(unique_ids),
            UploadedFile.incident_id == incident_id,
        )
        found = list((await self._session.scalars(stmt)).all())
        if len(found) != len(unique_ids):
            raise ValidationBusinessError(
                "One or more file_ids are invalid or do not belong to this incident.",
                error_code="INVALID_ANALYSIS_FILES",
            )
        for uploaded in found:
            if uploaded.validation_status != FileValidationStatus.VALID:
                raise ValidationBusinessError(
                    f"File '{uploaded.original_filename}' is not valid for analysis.",
                    error_code="INVALID_ANALYSIS_FILES",
                )
        return found

    async def _process_one(
        self,
        *,
        incident: Incident,
        uploader_id: UUID,
        original_name: str | None,
        raw: bytes,
        file_category: str | None,
        description: str | None,
    ) -> tuple[UploadedFile, str]:
        ensure_non_empty(raw)
        if len(raw) > self._settings.max_upload_size_bytes:
            raise FileTooLargeError(
                f"File exceeds maximum size of {self._settings.max_upload_size_bytes} bytes."
            )

        safe_name = sanitize_original_filename(original_name)
        _, file_type = detect_file_type(safe_name)
        text = decode_text_content(raw)

        try:
            validate_syntax(file_type, text)
        except Exception as exc:
            raise UnsupportedFileTypeError(
                f"File content failed {file_type.value} syntax validation."
            ) from exc

        masked_text, redaction_count = mask_secrets(text)
        checksum = hashlib.sha256(masked_text.encode("utf-8")).hexdigest()

        duplicate = await self._session.scalar(
            select(UploadedFile).where(
                UploadedFile.incident_id == incident.id,
                UploadedFile.checksum_sha256 == checksum,
            )
        )
        if duplicate is not None:
            raise DuplicateFileError()

        parser = get_parser_for(file_type)
        metadata: dict = {
            "file_category": file_category,
            "description": description,
            "redaction_count": redaction_count,
        }
        if parser is not None:
            metadata.update(
                parser.extract_metadata(content=masked_text, original_filename=safe_name)
            )

        file_id = uuid4()
        stored_filename = f"{file_id.hex}{PurePosixPath(safe_name).suffix.lower()}"
        relative_path = (
            f"org/{incident.project.organization_id}/"
            f"project/{incident.project_id}/"
            f"incident/{incident.id}/"
            f"{stored_filename}"
        )

        await self._storage.save(
            relative_path=relative_path,
            data=masked_text.encode("utf-8"),
        )

        mime, _ = mimetypes.guess_type(safe_name)
        record = UploadedFile(
            id=file_id,
            user_id=uploader_id,
            project_id=incident.project_id,
            pipeline_run_id=incident.pipeline_run_id,
            incident_id=incident.id,
            original_filename=safe_name,
            stored_filename=stored_filename,
            storage_path=relative_path,
            file_type=file_type,
            mime_type=mime or "text/plain",
            size_bytes=len(masked_text.encode("utf-8")),
            checksum_sha256=checksum,
            secret_masking_status=(
                SecretMaskingStatus.MASKED
                if redaction_count > 0
                else SecretMaskingStatus.NOT_REQUIRED
            ),
            validation_status=FileValidationStatus.VALID,
            processing_status=FileProcessingStatus.PENDING,
            extracted_metadata=metadata,
        )
        self._session.add(record)
        return record, relative_path

    async def _load_incident(self, organization_id: UUID, incident_id: UUID) -> Incident:
        stmt = (
            select(Incident)
            .join(Project, Project.id == Incident.project_id)
            .where(Incident.id == incident_id, Project.organization_id == organization_id)
            .options(selectinload(Incident.project))
        )
        incident = await self._session.scalar(stmt)
        if incident is None:
            raise ResourceNotFoundError("Incident not found.")
        return incident

    async def _load_file_in_org(self, organization_id: UUID, file_id: UUID) -> UploadedFile:
        stmt = (
            select(UploadedFile)
            .join(Project, Project.id == UploadedFile.project_id)
            .where(UploadedFile.id == file_id, Project.organization_id == organization_id)
        )
        uploaded = await self._session.scalar(stmt)
        if uploaded is None:
            raise ResourceNotFoundError("File not found.")
        return uploaded

    async def _assert_deletable(self, uploaded: UploadedFile) -> None:
        if uploaded.incident_id is None:
            return
        stmt = select(AnalysisRun).where(AnalysisRun.incident_id == uploaded.incident_id)
        runs = list((await self._session.scalars(stmt)).all())
        file_id_str = str(uploaded.id)
        for run in runs:
            input_summary = run.input_summary or {}
            file_ids = input_summary.get("file_ids") or []
            if file_id_str in file_ids:
                raise FileDeletionForbiddenError()
            if (
                run.status
                not in {
                    AnalysisRunStatus.FAILED,
                    AnalysisRunStatus.COMPLETED,
                }
                and run.status != AnalysisRunStatus.QUEUED
            ):
                # In-progress analysis on the incident blocks deletion of any file.
                raise FileDeletionForbiddenError(
                    "File cannot be deleted while analysis is in progress."
                )

    async def _record_event(
        self,
        *,
        incident_id: UUID,
        actor_id: UUID,
        title: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        self._session.add(
            IncidentEvent(
                incident_id=incident_id,
                event_type="file_deleted" if title.startswith("File deleted") else "file_uploaded",
                actor_type="user",
                actor_user_id=actor_id,
                title=title,
                description=description,
                event_metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _to_response(uploaded: UploadedFile) -> UploadedFileResponse:
        return UploadedFileResponse(
            id=uploaded.id,
            original_filename=uploaded.original_filename,
            file_type=uploaded.file_type.value,
            size_bytes=uploaded.size_bytes,
            checksum_sha256=uploaded.checksum_sha256,
            validation_status=uploaded.validation_status.value,
            secret_masking_status=uploaded.secret_masking_status.value,
            # API example uses "uploaded"; persisted enum uses pending after accept.
            processing_status=(
                "uploaded"
                if uploaded.processing_status == FileProcessingStatus.PENDING
                else uploaded.processing_status.value
            ),
            uploaded_at=uploaded.created_at,
            mime_type=uploaded.mime_type,
            incident_id=uploaded.incident_id,
            project_id=uploaded.project_id,
            pipeline_run_id=uploaded.pipeline_run_id,
        )


# Local import helper used above without top-level cycle risk.
from pathlib import PurePosixPath  # noqa: E402
