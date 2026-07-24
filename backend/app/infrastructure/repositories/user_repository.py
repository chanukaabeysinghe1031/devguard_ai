"""SQLAlchemy user repository implementation."""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import UserEntity
from app.domain.exceptions.repository import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
)
from app.domain.interfaces.repositories import UserRepository
from app.infrastructure.database.models.user import User
from app.infrastructure.repositories.base import SQLAlchemyAsyncRepository

logger = structlog.get_logger(__name__)


def _to_entity(model: User) -> UserEntity:
    return UserEntity(
        id=model.id,
        email=model.email,
        password_hash=model.password_hash,
        full_name=model.full_name,
        platform_role=model.platform_role,
        avatar_url=model.avatar_url,
        is_active=model.is_active,
        last_login_at=model.last_login_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_model(entity: UserEntity) -> User:
    return User(
        id=entity.id,
        email=entity.email,
        password_hash=entity.password_hash,
        full_name=entity.full_name,
        platform_role=entity.platform_role,
        avatar_url=entity.avatar_url,
        is_active=entity.is_active,
        last_login_at=entity.last_login_at,
    )


class SQLAlchemyUserRepository(SQLAlchemyAsyncRepository[User], UserRepository):
    """Async SQLAlchemy implementation of UserRepository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_id(self, entity_id: UUID) -> UserEntity | None:
        model = await super().get_by_id(entity_id)
        return _to_entity(model) if model is not None else None

    async def get_by_email(self, email: str) -> UserEntity | None:
        try:
            stmt = select(User).where(func.lower(User.email) == email.lower())
            model = await self._session.scalar(stmt)
            return _to_entity(model) if model is not None else None
        except SQLAlchemyError as exc:
            logger.exception("repository_get_by_email_failed")
            raise RepositoryError("Failed to retrieve user by email.") from exc

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[UserEntity]:
        models = await super().list(offset=offset, limit=limit)
        return [_to_entity(model) for model in models]

    async def add(self, entity: UserEntity) -> UserEntity:
        existing = await self.get_by_email(entity.email)
        if existing is not None:
            raise DuplicateEntityError(f"User with email '{entity.email}' already exists.")

        model = _to_model(entity)
        try:
            persisted = await super().add(model)
        except IntegrityError as exc:
            logger.warning("repository_duplicate_user_email", email=entity.email)
            raise DuplicateEntityError(f"User with email '{entity.email}' already exists.") from exc
        return _to_entity(persisted)

    async def update(self, entity: UserEntity) -> UserEntity:
        if entity.id is None:
            raise RepositoryError("Cannot update a user without an id.")

        model = await self._session.get(User, entity.id)
        if model is None:
            raise EntityNotFoundError(f"User '{entity.id}' not found.")

        if model.email.lower() != entity.email.lower():
            existing = await self.get_by_email(entity.email)
            if existing is not None and existing.id != entity.id:
                raise DuplicateEntityError(f"User with email '{entity.email}' already exists.")

        model.email = entity.email
        model.password_hash = entity.password_hash
        model.full_name = entity.full_name
        model.platform_role = entity.platform_role
        model.avatar_url = entity.avatar_url
        model.is_active = entity.is_active
        model.last_login_at = entity.last_login_at

        try:
            persisted = await super().update(model)
        except IntegrityError as exc:
            logger.warning("repository_duplicate_user_email", email=entity.email)
            raise DuplicateEntityError(f"User with email '{entity.email}' already exists.") from exc
        return _to_entity(persisted)

    async def delete(self, entity: UserEntity) -> None:
        raise RepositoryError("Physical user deletion is not supported. Use deactivate().")

    async def deactivate(self, user_id: UUID) -> UserEntity:
        model = await self._session.get(User, user_id)
        if model is None:
            raise EntityNotFoundError(f"User '{user_id}' not found.")

        model.is_active = False
        persisted = await super().update(model)
        return _to_entity(persisted)
