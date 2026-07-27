"""Project management application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import project_detail, project_list_item, project_to_response
from app.domain.enums import CiProvider, IncidentStatus, PipelineRunStatus, ProjectStatus
from app.domain.exceptions.business import (
    ConflictError,
    ResourceNotFoundError,
    ValidationBusinessError,
)
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.project import Project
from app.schemas.common import PaginatedResponse, build_paginated_response, normalize_pagination
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectDetailResponse,
    ProjectListItem,
    ProjectResponse,
    ProjectStatistics,
    ProjectUpdateRequest,
)

logger = structlog.get_logger(__name__)

_OPEN_INCIDENT_STATUSES = (
    IncidentStatus.DETECTED,
    IncidentStatus.ANALYSING,
    IncidentStatus.OPEN,
    IncidentStatus.IN_PROGRESS,
    IncidentStatus.ANALYSIS_FAILED,
    IncidentStatus.REOPENED,
)


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        created_by: UUID,
        body: ProjectCreateRequest,
    ) -> ProjectResponse:
        try:
            ci_provider = CiProvider(body.ci_provider)
        except ValueError as exc:
            raise ValidationBusinessError(f"Invalid ci_provider '{body.ci_provider}'.") from exc

        project = Project(
            organization_id=organization_id,
            name=body.name.strip(),
            key=body.key.strip().upper(),
            description=body.description,
            repository_url=body.repository_url,
            default_branch=body.default_branch,
            ci_provider=ci_provider,
            cloud_provider=body.cloud_provider,
            default_environment=body.default_environment,
            status=ProjectStatus.ACTIVE,
            created_by=created_by,
        )
        self._session.add(project)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A project with this key already exists in the organization.",
                error_code="DUPLICATE_PROJECT_KEY",
            ) from exc
        logger.info("project_created", project_id=str(project.id))
        return project_to_response(project)

    async def list_projects(
        self,
        *,
        organization_id: UUID,
        page: int,
        page_size: int,
        status: str | None = None,
        ci_provider: str | None = None,
        cloud_provider: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResponse[ProjectListItem]:
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [Project.organization_id == organization_id]
        if status:
            filters.append(Project.status == ProjectStatus(status))
        if ci_provider:
            filters.append(Project.ci_provider == CiProvider(ci_provider))
        if cloud_provider:
            filters.append(Project.cloud_provider == cloud_provider)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(Project.name.ilike(pattern) | Project.key.ilike(pattern))

        count_stmt = select(func.count()).select_from(Project).where(*filters)
        total = int(await self._session.scalar(count_stmt) or 0)

        order_col = Project.created_at if sort_by != "name" else Project.name
        order = order_col.desc() if sort_order == "desc" else order_col.asc()
        stmt = select(Project).where(*filters).order_by(order).offset(offset).limit(page_size)
        projects = list((await self._session.scalars(stmt)).all())

        items: list[ProjectListItem] = []
        for project in projects:
            open_count = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(Incident)
                    .where(
                        Incident.project_id == project.id,
                        Incident.status.in_(_OPEN_INCIDENT_STATUSES),
                    )
                )
                or 0
            )
            last_run_at = await self._session.scalar(
                select(func.max(PipelineRun.created_at)).where(PipelineRun.project_id == project.id)
            )
            items.append(
                project_list_item(
                    project,
                    open_incident_count=open_count,
                    last_pipeline_run_at=last_run_at,
                )
            )

        return build_paginated_response(
            items=items, page=page, page_size=page_size, total_items=total
        )

    async def get(self, *, organization_id: UUID, project_id: UUID) -> ProjectDetailResponse:
        project = await self._get_project(organization_id, project_id)
        stats = await self._statistics(project.id)
        return project_detail(project, stats)

    async def update(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        body: ProjectUpdateRequest,
    ) -> ProjectResponse:
        project = await self._get_project(organization_id, project_id)
        if project.status == ProjectStatus.ARCHIVED:
            raise ValidationBusinessError("Archived projects cannot be updated.")
        if body.description is not None:
            project.description = body.description
        if body.repository_url is not None:
            project.repository_url = body.repository_url
        if body.default_branch is not None:
            project.default_branch = body.default_branch
        if body.cloud_provider is not None:
            project.cloud_provider = body.cloud_provider
        if body.default_environment is not None:
            project.default_environment = body.default_environment
        await self._session.flush()
        return project_to_response(project)

    async def archive(self, *, organization_id: UUID, project_id: UUID) -> None:
        project = await self._get_project(organization_id, project_id)
        project.status = ProjectStatus.ARCHIVED
        project.archived_at = datetime.now(UTC)
        await self._session.flush()

    async def restore(self, *, organization_id: UUID, project_id: UUID) -> None:
        project = await self._get_project(organization_id, project_id)
        project.status = ProjectStatus.ACTIVE
        project.archived_at = None
        await self._session.flush()

    async def _get_project(self, organization_id: UUID, project_id: UUID) -> Project:
        project = await self._session.get(Project, project_id)
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFoundError("Project not found.")
        return project

    async def _statistics(self, project_id: UUID) -> ProjectStatistics:
        total_runs = int(
            await self._session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(PipelineRun.project_id == project_id)
            )
            or 0
        )
        failed_runs = int(
            await self._session.scalar(
                select(func.count())
                .select_from(PipelineRun)
                .where(
                    PipelineRun.project_id == project_id,
                    PipelineRun.status == PipelineRunStatus.FAILED,
                )
            )
            or 0
        )
        open_incidents = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Incident)
                .where(
                    Incident.project_id == project_id,
                    Incident.status.in_(_OPEN_INCIDENT_STATUSES),
                )
            )
            or 0
        )
        resolved_incidents = int(
            await self._session.scalar(
                select(func.count())
                .select_from(Incident)
                .where(
                    Incident.project_id == project_id,
                    Incident.status.in_((IncidentStatus.RESOLVED, IncidentStatus.CLOSED)),
                )
            )
            or 0
        )
        return ProjectStatistics(
            total_pipeline_runs=total_runs,
            failed_pipeline_runs=failed_runs,
            open_incidents=open_incidents,
            resolved_incidents=resolved_incidents,
        )
