"""SQLAlchemy pipeline run repository implementation."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.pipeline_run import PipelineRunEntity
from app.domain.enums import PipelineRunStatus
from app.domain.exceptions.repository import EntityNotFoundError, RepositoryError
from app.domain.interfaces.repositories import PipelineRunRepository
from app.infrastructure.database.models.pipeline_run import PipelineRun
from app.infrastructure.repositories.base import SQLAlchemyAsyncRepository

logger = structlog.get_logger(__name__)


def _to_entity(model: PipelineRun) -> PipelineRunEntity:
    return PipelineRunEntity(
        id=model.id,
        project_id=model.project_id,
        provider=model.provider,
        status=model.status,
        external_run_id=model.external_run_id,
        workflow_name=model.workflow_name,
        branch=model.branch,
        commit_sha=model.commit_sha,
        triggered_by=model.triggered_by,
        environment=model.environment,
        started_at=model.started_at,
        completed_at=model.completed_at,
        duration_seconds=model.duration_seconds,
        source_url=model.source_url,
        raw_metadata=model.raw_metadata,
        created_at=model.created_at,
    )


def _to_model(entity: PipelineRunEntity) -> PipelineRun:
    return PipelineRun(
        id=entity.id,
        project_id=entity.project_id,
        provider=entity.provider,
        status=entity.status,
        external_run_id=entity.external_run_id,
        workflow_name=entity.workflow_name,
        branch=entity.branch,
        commit_sha=entity.commit_sha,
        triggered_by=entity.triggered_by,
        environment=entity.environment,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
        duration_seconds=entity.duration_seconds,
        source_url=entity.source_url,
        raw_metadata=entity.raw_metadata,
    )


class SQLAlchemyPipelineRunRepository(
    SQLAlchemyAsyncRepository[PipelineRun],
    PipelineRunRepository,
):
    """Async SQLAlchemy implementation of PipelineRunRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PipelineRun)

    async def get_by_id(self, entity_id: UUID) -> PipelineRunEntity | None:
        model = await super().get_by_id(entity_id)
        return _to_entity(model) if model is not None else None

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[PipelineRunEntity]:
        try:
            stmt = (
                select(PipelineRun)
                .where(PipelineRun.project_id == project_id)
                .order_by(PipelineRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            return [_to_entity(model) for model in result.all()]
        except SQLAlchemyError as exc:
            logger.exception("repository_list_by_project_failed", project_id=str(project_id))
            raise RepositoryError("Failed to list pipeline runs for project.") from exc

    async def list_by_status(
        self,
        status: PipelineRunStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[PipelineRunEntity]:
        try:
            stmt = (
                select(PipelineRun)
                .where(PipelineRun.status == status)
                .order_by(PipelineRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            return [_to_entity(model) for model in result.all()]
        except SQLAlchemyError as exc:
            logger.exception("repository_list_by_status_failed", status=status.value)
            raise RepositoryError("Failed to list pipeline runs by status.") from exc

    # NOTE: defined after list_by_project/list_by_status so that mypy resolves
    # the builtin `list[...]` in their return annotations before this method's
    # name shadows it within the class namespace.
    async def list(self, *, offset: int = 0, limit: int = 100) -> list[PipelineRunEntity]:
        try:
            stmt = (
                select(PipelineRun)
                .order_by(PipelineRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            return [_to_entity(model) for model in result.all()]
        except SQLAlchemyError as exc:
            logger.exception("repository_list_failed", model="PipelineRun")
            raise RepositoryError("Failed to list pipeline runs.") from exc

    async def add(self, entity: PipelineRunEntity) -> PipelineRunEntity:
        model = _to_model(entity)
        persisted = await super().add(model)
        return _to_entity(persisted)

    async def update(self, entity: PipelineRunEntity) -> PipelineRunEntity:
        if entity.id is None:
            raise RepositoryError("Cannot update a pipeline run without an id.")

        model = await self._session.get(PipelineRun, entity.id)
        if model is None:
            raise EntityNotFoundError(f"Pipeline run '{entity.id}' not found.")

        model.project_id = entity.project_id
        model.provider = entity.provider
        model.status = entity.status
        model.external_run_id = entity.external_run_id
        model.workflow_name = entity.workflow_name
        model.branch = entity.branch
        model.commit_sha = entity.commit_sha
        model.triggered_by = entity.triggered_by
        model.environment = entity.environment
        model.started_at = entity.started_at
        model.completed_at = entity.completed_at
        model.duration_seconds = entity.duration_seconds
        model.source_url = entity.source_url
        model.raw_metadata = entity.raw_metadata

        persisted = await super().update(model)
        return _to_entity(persisted)

    async def delete(self, entity: PipelineRunEntity) -> None:
        if entity.id is None:
            raise RepositoryError("Cannot delete a pipeline run without an id.")

        model = await self._session.get(PipelineRun, entity.id)
        if model is None:
            raise EntityNotFoundError(f"Pipeline run '{entity.id}' not found.")

        await super().delete(model)
