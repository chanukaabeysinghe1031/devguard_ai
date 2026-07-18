"""Generic async SQLAlchemy repository base."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions.repository import RepositoryError

logger = structlog.get_logger(__name__)

ModelT = TypeVar("ModelT")


class SQLAlchemyAsyncRepository(Generic[ModelT]):
    """Shared SQLAlchemy persistence helpers."""

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        try:
            return await self._session.get(self._model, entity_id)
        except SQLAlchemyError as exc:
            logger.exception("repository_get_by_id_failed", model=self._model.__name__)
            raise RepositoryError("Failed to retrieve entity.") from exc

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[ModelT]:
        try:
            stmt = select(self._model).offset(offset).limit(limit)
            result = await self._session.scalars(stmt)
            return list(result.all())
        except SQLAlchemyError as exc:
            logger.exception("repository_list_failed", model=self._model.__name__)
            raise RepositoryError("Failed to list entities.") from exc

    async def add(self, entity: ModelT) -> ModelT:
        try:
            self._session.add(entity)
            await self._session.flush()
            await self._session.refresh(entity)
            return entity
        except SQLAlchemyError as exc:
            logger.exception("repository_add_failed", model=self._model.__name__)
            raise RepositoryError("Failed to add entity.") from exc

    async def update(self, entity: ModelT) -> ModelT:
        try:
            await self._session.flush()
            await self._session.refresh(entity)
            return entity
        except SQLAlchemyError as exc:
            logger.exception("repository_update_failed", model=self._model.__name__)
            raise RepositoryError("Failed to update entity.") from exc

    async def delete(self, entity: ModelT) -> None:
        try:
            await self._session.delete(entity)
            await self._session.flush()
        except SQLAlchemyError as exc:
            logger.exception("repository_delete_failed", model=self._model.__name__)
            raise RepositoryError("Failed to delete entity.") from exc
