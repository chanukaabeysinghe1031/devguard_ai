"""Secure file upload endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.access import require_org_reader, require_org_writer
from app.application.services.upload_service import UploadService
from app.core.config import Settings
from app.domain.exceptions.upload import StorageConfigurationError, TooManyFilesError
from app.infrastructure.storage import build_file_storage
from app.schemas.file import FileDetailResponse, FileListResponse, UploadFilesResponse

router = APIRouter(tags=["Files"])


def _upload_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> UploadService:
    try:
        storage = build_file_storage(settings)
    except StorageConfigurationError as exc:
        from app.domain.exceptions.business import ValidationBusinessError

        raise ValidationBusinessError(str(exc), error_code="STORAGE_MISCONFIGURED") from exc
    return UploadService(session=session, settings=settings, storage=storage)


@router.post(
    "/incidents/{incident_id}/files",
    response_model=UploadFilesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_incident_files(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: UploadService = Depends(_upload_service),
    files: list[UploadFile] = File(...),
    file_category: str | None = Form(default=None),
    description: str | None = Form(default=None),
) -> UploadFilesResponse:
    user, organization_id, _ = ctx
    settings = service._settings
    if len(files) > settings.max_files_per_upload:
        raise TooManyFilesError()

    payloads: list[tuple[str | None, bytes]] = []
    for upload in files:
        # Read with a hard cap slightly above max to reject oversized bodies early.
        data = await upload.read(settings.max_upload_size_bytes + 1)
        payloads.append((upload.filename, data))

    return await service.upload_incident_files(
        organization_id=organization_id,
        incident_id=incident_id,
        uploader_id=user.id,
        files=payloads,
        file_category=file_category,
        description=description,
    )


@router.get("/incidents/{incident_id}/files", response_model=FileListResponse)
async def list_incident_files(
    incident_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: UploadService = Depends(_upload_service),
) -> FileListResponse:
    _, organization_id, _ = ctx
    return await service.list_incident_files(
        organization_id=organization_id,
        incident_id=incident_id,
    )


@router.get("/files/{file_id}", response_model=FileDetailResponse)
async def get_file_metadata(
    file_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: UploadService = Depends(_upload_service),
) -> FileDetailResponse:
    _, organization_id, _ = ctx
    return await service.get_file(organization_id=organization_id, file_id=file_id)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: UploadService = Depends(_upload_service),
) -> None:
    user, organization_id, _ = ctx
    await service.delete_file(
        organization_id=organization_id,
        file_id=file_id,
        actor_id=user.id,
    )
