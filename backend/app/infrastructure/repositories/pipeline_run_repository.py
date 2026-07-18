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
        user_id=model.user_id,
        uploaded_file_id=model.uploaded_file_id,
        workflow_file_id=model.workflow_file_id,
        status=model.status,
        platform=model.platform,
        pipeline_name=model.pipeline_name,
        job_name=model.job_name,
        started_at=model.started_at,
        finished_at=model.finished_at,
        raw_log_excerpt=model.raw_log_excerpt,
        run_metadata=model.run_metadata,
        created_at=model.created_at,
    )


def _to_model(entity: PipelineRunEntity) -> PipelineRun:
    return PipelineRun(
        id=entity.id,
        user_id=entity.user_id,
        uploaded_file_id=entity.uploaded_file_id,
        workflow_file_id=entity.workflow_file_id,
        status=entity.status,
        platform=entity.platform,
        pipeline_name=entity.pipeline_name,
        job_name=entity.job_name,
        started_at=entity.started_at,
        finished_at=entity.finished_at,
        raw_log_excerpt=entity.raw_log_excerpt,
        run_metadata=entity.run_metadata or {},
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

    async def list_by_user(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[PipelineRunEntity]:
        try:
            stmt = (
                select(PipelineRun)
                .where(PipelineRun.user_id == user_id)
                .order_by(PipelineRun.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            return [_to_entity(model) for model in result.all()]
        except SQLAlchemyError as exc:
            logger.exception("repository_list_by_user_failed", user_id=str(user_id))
            raise RepositoryError("Failed to list pipeline runs for user.") from exc

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

        model.user_id = entity.user_id
        model.uploaded_file_id = entity.uploaded_file_id
        model.workflow_file_id = entity.workflow_file_id
        model.status = entity.status
        model.platform = entity.platform
        model.pipeline_name = entity.pipeline_name
        model.job_name = entity.job_name
        model.started_at = entity.started_at
        model.finished_at = entity.finished_at
        model.raw_log_excerpt = entity.raw_log_excerpt
        model.run_metadata = entity.run_metadata or {}

        persisted = await super().update(model)
        return _to_entity(persisted)

    async def delete(self, entity: PipelineRunEntity) -> None:
        if entity.id is None:
            raise RepositoryError("Cannot delete a pipeline run without an id.")

        model = await self._session.get(PipelineRun, entity.id)
        if model is None:
            raise EntityNotFoundError(f"Pipeline run '{entity.id}' not found.")

        await super().delete(model)
