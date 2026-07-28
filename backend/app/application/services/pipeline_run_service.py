"""Pipeline run application service."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mappers import pipeline_run_to_response
from app.domain.enums import CiProvider, PipelineRunStatus, ProjectStatus
from app.domain.exceptions.business import ResourceNotFoundError, ValidationBusinessError
from app.infrastructure.database.models.incident import Incident
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.database.models.project import Project
from app.schemas.common import PaginatedResponse, build_paginated_response, normalize_pagination
from app.schemas.pipeline_run import PipelineRunCreateRequest, PipelineRunResponse

logger = structlog.get_logger(__name__)


class PipelineRunService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        body: PipelineRunCreateRequest,
    ) -> PipelineRunResponse:
        project = await self._get_active_project(organization_id, project_id)
        try:
            provider = CiProvider(body.provider)
            status = PipelineRunStatus(body.status)
        except ValueError as exc:
            raise ValidationBusinessError("Invalid provider or status value.") from exc

        duration = None
        if body.started_at and body.completed_at:
            duration = int((body.completed_at - body.started_at).total_seconds())

        run = PipelineRun(
            project_id=project.id,
            external_run_id=body.external_run_id,
            provider=provider,
            workflow_name=body.workflow_name,
            branch=body.branch,
            commit_sha=body.commit_sha,
            triggered_by=body.triggered_by,
            environment=body.environment,
            status=status,
            started_at=body.started_at,
            completed_at=body.completed_at,
            duration_seconds=duration,
            source_url=body.source_url,
            raw_metadata=body.raw_metadata,
        )
        self._session.add(run)
        await self._session.flush()
        logger.info("pipeline_run_created", pipeline_run_id=str(run.id))
        return pipeline_run_to_response(run, incident_count=0)

    async def list_for_project(
        self,
        *,
        organization_id: UUID,
        project_id: UUID,
        page: int,
        page_size: int,
        status: str | None = None,
        provider: str | None = None,
        environment: str | None = None,
        branch: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PaginatedResponse[PipelineRunResponse]:
        await self._get_project(organization_id, project_id)
        page, page_size, offset = normalize_pagination(page, page_size)
        filters = [PipelineRun.project_id == project_id]
        if status:
            filters.append(PipelineRun.status == PipelineRunStatus(status))
        if provider:
            filters.append(PipelineRun.provider == CiProvider(provider))
        if environment:
            filters.append(PipelineRun.environment == environment)
        if branch:
            filters.append(PipelineRun.branch == branch)
        if date_from:
            filters.append(PipelineRun.created_at >= date_from)
        if date_to:
            filters.append(PipelineRun.created_at <= date_to)

        total = int(
            await self._session.scalar(
                select(func.count()).select_from(PipelineRun).where(*filters)
            )
            or 0
        )
        stmt = (
            select(PipelineRun)
            .where(*filters)
            .order_by(PipelineRun.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        runs = list((await self._session.scalars(stmt)).all())
        items: list[PipelineRunResponse] = []
        for run in runs:
            count = int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(Incident)
                    .where(Incident.pipeline_run_id == run.id)
                )
                or 0
            )
            items.append(pipeline_run_to_response(run, incident_count=count))
        return build_paginated_response(
            items=items, page=page, page_size=page_size, total_items=total
        )

    async def get(
        self,
        *,
        organization_id: UUID,
        pipeline_run_id: UUID,
    ) -> PipelineRunResponse:
        run = await self._session.get(PipelineRun, pipeline_run_id)
        if run is None:
            raise ResourceNotFoundError("Pipeline run not found.")
        project = await self._get_project(organization_id, run.project_id)
        if project.id != run.project_id:
            raise ResourceNotFoundError("Pipeline run not found.")
        count = int(
            await self._session.scalar(
                select(func.count()).select_from(Incident).where(Incident.pipeline_run_id == run.id)
            )
            or 0
        )
        return pipeline_run_to_response(run, incident_count=count)

    async def _get_project(self, organization_id: UUID, project_id: UUID) -> Project:
        project = await self._session.get(Project, project_id)
        if project is None or project.organization_id != organization_id:
            raise ResourceNotFoundError("Project not found.")
        return project

    async def _get_active_project(self, organization_id: UUID, project_id: UUID) -> Project:
        project = await self._get_project(organization_id, project_id)
        if project.status == ProjectStatus.ARCHIVED:
            raise ValidationBusinessError("Cannot create pipeline runs for an archived project.")
        return project
