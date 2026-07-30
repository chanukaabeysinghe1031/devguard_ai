"""Incident report endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.api.deps.access import require_org_reader, require_org_writer
from app.application.services.report_service import ReportService
from app.core.config import Settings
from app.domain.exceptions.business import ValidationBusinessError
from app.domain.exceptions.upload import StorageConfigurationError
from app.infrastructure.storage import build_file_storage
from app.schemas.report import ReportDetailResponse, ReportGenerateResponse, ReportListResponse

router = APIRouter(prefix="/reports", tags=["Reports"])


def _report_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> ReportService:
    try:
        storage = build_file_storage(settings)
    except StorageConfigurationError as exc:
        raise ValidationBusinessError(str(exc), error_code="STORAGE_MISCONFIGURED") from exc
    return ReportService(session=session, storage=storage)


@router.get("", response_model=ReportListResponse)
async def list_reports(
    ctx: tuple = Depends(require_org_reader),
    service: ReportService = Depends(_report_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    incident_id: UUID | None = None,
    project_id: UUID | None = None,
) -> ReportListResponse:
    _, organization_id, _ = ctx
    return await service.list_reports(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        incident_id=incident_id,
        project_id=project_id,
    )


@router.get("/{report_id}", response_model=ReportDetailResponse)
async def get_report(
    report_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: ReportService = Depends(_report_service),
) -> ReportDetailResponse:
    _, organization_id, _ = ctx
    return await service.get_report(organization_id=organization_id, report_id=report_id)


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: ReportService = Depends(_report_service),
) -> Response:
    _, organization_id, _ = ctx
    report, data = await service.download_bytes(
        organization_id=organization_id,
        report_id=report_id,
    )
    media_type = "application/json" if report.format == "json" else "application/octet-stream"
    filename = f"incident-report-{report.incident_id}.{report.format}"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
