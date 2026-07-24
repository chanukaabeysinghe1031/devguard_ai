"""SQLAlchemy failure category repository implementation."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.failure_category import FailureCategoryEntity
from app.domain.exceptions.repository import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
)
from app.domain.interfaces.repositories import FailureCategoryRepository
from app.infrastructure.database.models.failure_category import FailureCategory
from app.infrastructure.repositories.base import SQLAlchemyAsyncRepository

logger = structlog.get_logger(__name__)


def _to_entity(model: FailureCategory) -> FailureCategoryEntity:
    return FailureCategoryEntity(
        id=model.id,
        name=model.name,
        code=model.code,
        description=model.description,
        is_active=model.is_active,
        created_at=model.created_at,
    )


def _to_model(entity: FailureCategoryEntity) -> FailureCategory:
    return FailureCategory(
        id=entity.id,
        name=entity.name,
        code=entity.code,
        description=entity.description,
        is_active=entity.is_active,
    )


class SQLAlchemyFailureCategoryRepository(
    SQLAlchemyAsyncRepository[FailureCategory],
    FailureCategoryRepository,
):
    """Async SQLAlchemy implementation of FailureCategoryRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FailureCategory)

    async def get_by_id(self, entity_id: UUID) -> FailureCategoryEntity | None:
        model = await super().get_by_id(entity_id)
        return _to_entity(model) if model is not None else None

    async def get_by_code(self, code: str) -> FailureCategoryEntity | None:
        try:
            normalized_code = code.lower()
            stmt = select(FailureCategory).where(FailureCategory.code == normalized_code)
            model = await self._session.scalar(stmt)
            return _to_entity(model) if model is not None else None
        except SQLAlchemyError as exc:
            logger.exception("repository_get_by_code_failed", code=code)
            raise RepositoryError("Failed to retrieve failure category by code.") from exc

    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[FailureCategoryEntity]:
        try:
            stmt = (
                select(FailureCategory)
                .where(FailureCategory.is_active.is_(True))
                .order_by(FailureCategory.code)
                .offset(offset)
                .limit(limit)
            )
            result = await self._session.scalars(stmt)
            return [_to_entity(model) for model in result.all()]
        except SQLAlchemyError as exc:
            logger.exception("repository_list_active_failed")
            raise RepositoryError("Failed to list active failure categories.") from exc

    # NOTE: defined after list_active so that mypy resolves the builtin
    # `list[...]` in its return annotation before this method's name shadows
    # it within the class namespace.
    async def list(self, *, offset: int = 0, limit: int = 100) -> list[FailureCategoryEntity]:
        models = await super().list(offset=offset, limit=limit)
        return [_to_entity(model) for model in models]

    async def add(self, entity: FailureCategoryEntity) -> FailureCategoryEntity:
        normalized_code = entity.code.lower()
        existing = await self.get_by_code(normalized_code)
        if existing is not None:
            raise DuplicateEntityError(
                f"Failure category with code '{normalized_code}' already exists."
            )

        entity.code = normalized_code
        model = _to_model(entity)
        try:
            persisted = await super().add(model)
        except IntegrityError as exc:
            logger.warning("repository_duplicate_failure_category", code=normalized_code)
            raise DuplicateEntityError(
                f"Failure category with code '{normalized_code}' already exists."
            ) from exc
        return _to_entity(persisted)

    async def update(self, entity: FailureCategoryEntity) -> FailureCategoryEntity:
        if entity.id is None:
            raise RepositoryError("Cannot update a failure category without an id.")

        model = await self._session.get(FailureCategory, entity.id)
        if model is None:
            raise EntityNotFoundError(f"Failure category '{entity.id}' not found.")

        normalized_code = entity.code.lower()
        if model.code != normalized_code:
            existing = await self.get_by_code(normalized_code)
            if existing is not None and existing.id != entity.id:
                raise DuplicateEntityError(
                    f"Failure category with code '{normalized_code}' already exists."
                )

        model.name = entity.name
        model.code = normalized_code
        model.description = entity.description
        model.is_active = entity.is_active

        try:
            persisted = await super().update(model)
        except IntegrityError as exc:
            logger.warning("repository_duplicate_failure_category", code=normalized_code)
            raise DuplicateEntityError(
                f"Failure category with code '{normalized_code}' already exists."
            ) from exc
        return _to_entity(persisted)

    async def delete(self, entity: FailureCategoryEntity) -> None:
        raise RepositoryError("Failure category deletion is not supported.")
