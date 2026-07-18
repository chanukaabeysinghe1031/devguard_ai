"""Async repository contracts (domain boundary, no SQLAlchemy)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from app.domain.entities.failure_category import FailureCategoryEntity
from app.domain.entities.pipeline_run import PipelineRunEntity
from app.domain.entities.user import UserEntity
from app.domain.enums import PipelineRunStatus

T = TypeVar("T")


class AsyncRepository(ABC, Generic[T]):
    """Generic async repository contract."""

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> T | None:
        """Return an entity by primary key."""

    @abstractmethod
    async def list(self, *, offset: int = 0, limit: int = 100) -> list[T]:
        """Return a paginated list of entities."""

    @abstractmethod
    async def add(self, entity: T) -> T:
        """Persist a new entity."""

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Persist changes to an existing entity."""

    @abstractmethod
    async def delete(self, entity: T) -> None:
        """Remove an entity."""


class UserRepository(AsyncRepository[UserEntity], ABC):
    """User persistence contract."""

    @abstractmethod
    async def get_by_email(self, email: str) -> UserEntity | None:
        """Return a user by email (case-insensitive)."""

    @abstractmethod
    async def deactivate(self, user_id: UUID) -> UserEntity:
        """Soft-deactivate a user by setting is_active to false."""


class FailureCategoryRepository(AsyncRepository[FailureCategoryEntity], ABC):
    """Failure category persistence contract."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> FailureCategoryEntity | None:
        """Return a category by stable lowercase slug."""

    @abstractmethod
    async def list_active(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[FailureCategoryEntity]:
        """Return only active categories."""


class PipelineRunRepository(AsyncRepository[PipelineRunEntity], ABC):
    """Pipeline run persistence contract."""

    @abstractmethod
    async def list_by_user(
        self,
        user_id: UUID,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[PipelineRunEntity]:
        """Return a user's pipeline runs ordered by created_at descending."""

    @abstractmethod
    async def list_by_status(
        self,
        status: PipelineRunStatus,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> list[PipelineRunEntity]:
        """Return pipeline runs filtered by status."""
