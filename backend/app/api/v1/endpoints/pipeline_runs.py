"""Pipeline run endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_reader, require_org_writer
from app.application.services.pipeline_run_service import PipelineRunService
from app.schemas.common import PaginatedResponse
from app.schemas.pipeline_run import PipelineRunCreateRequest, PipelineRunResponse

router = APIRouter(tags=["Pipeline Runs"])


def _service(session: AsyncSession = Depends(get_session)) -> PipelineRunService:
    return PipelineRunService(session)


@router.post(
    "/projects/{project_id}/pipeline-runs",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline_run(
    project_id: UUID,
    body: PipelineRunCreateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: PipelineRunService = Depends(_service),
) -> PipelineRunResponse:
    _, organization_id, _ = ctx
    return await service.create(
        organization_id=organization_id,
        project_id=project_id,
        body=body,
    )


@router.get(
    "/projects/{project_id}/pipeline-runs",
    response_model=PaginatedResponse[PipelineRunResponse],
)
async def list_pipeline_runs(
    project_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: PipelineRunService = Depends(_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    provider: str | None = None,
    environment: str | None = None,
    branch: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> PaginatedResponse[PipelineRunResponse]:
    _, organization_id, _ = ctx
    return await service.list_for_project(
        organization_id=organization_id,
        project_id=project_id,
        page=page,
        page_size=page_size,
        status=status,
        provider=provider,
        environment=environment,
        branch=branch,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/pipeline-runs/{pipeline_run_id}", response_model=PipelineRunResponse)
async def get_pipeline_run(
    pipeline_run_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: PipelineRunService = Depends(_service),
) -> PipelineRunResponse:
    _, organization_id, _ = ctx
    return await service.get(
        organization_id=organization_id,
        pipeline_run_id=pipeline_run_id,
    )
