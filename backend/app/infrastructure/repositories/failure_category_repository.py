"""Failure category repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import FailureCategory
from app.infrastructure.repositories.base import BaseRepository


class FailureCategoryRepository(BaseRepository[FailureCategory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FailureCategory)

    async def get_by_slug(self, slug: str) -> FailureCategory | None:
        stmt = select(FailureCategory).where(FailureCategory.slug == slug)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[FailureCategory]:
        stmt = select(FailureCategory).where(FailureCategory.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
