"""Project management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.api.deps.access import require_org_admin, require_org_reader, require_org_writer
from app.application.services.project_service import ProjectService
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdateRequest,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def _service(session: AsyncSession = Depends(get_session)) -> ProjectService:
    return ProjectService(session)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: ProjectService = Depends(_service),
) -> ProjectResponse:
    user, organization_id, _ = ctx
    return await service.create(
        organization_id=organization_id,
        created_by=user.id,
        body=body,
    )


@router.get("", response_model=PaginatedResponse[ProjectListItem])
async def list_projects(
    ctx: tuple = Depends(require_org_reader),
    service: ProjectService = Depends(_service),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
    ci_provider: str | None = None,
    cloud_provider: str | None = None,
    search: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
) -> PaginatedResponse[ProjectListItem]:
    _, organization_id, _ = ctx
    return await service.list_projects(
        organization_id=organization_id,
        page=page,
        page_size=page_size,
        status=status,
        ci_provider=ci_provider,
        cloud_provider=cloud_provider,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: UUID,
    ctx: tuple = Depends(require_org_reader),
    service: ProjectService = Depends(_service),
) -> ProjectDetailResponse:
    _, organization_id, _ = ctx
    return await service.get(organization_id=organization_id, project_id=project_id)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    ctx: tuple = Depends(require_org_writer),
    service: ProjectService = Depends(_service),
) -> ProjectResponse:
    _, organization_id, _ = ctx
    return await service.update(
        organization_id=organization_id,
        project_id=project_id,
        body=body,
    )


@router.post("/{project_id}/archive", response_model=MessageResponse)
async def archive_project(
    project_id: UUID,
    ctx: tuple = Depends(require_org_admin),
    service: ProjectService = Depends(_service),
) -> MessageResponse:
    _, organization_id, _ = ctx
    await service.archive(organization_id=organization_id, project_id=project_id)
    return MessageResponse(message="Project archived successfully.")


@router.post("/{project_id}/restore", response_model=MessageResponse)
async def restore_project(
    project_id: UUID,
    ctx: tuple = Depends(require_org_writer),
    service: ProjectService = Depends(_service),
) -> MessageResponse:
    _, organization_id, _ = ctx
    await service.restore(organization_id=organization_id, project_id=project_id)
    return MessageResponse(message="Project restored successfully.")
