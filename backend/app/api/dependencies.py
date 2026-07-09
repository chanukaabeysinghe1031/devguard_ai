"""FastAPI dependency injection providers."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.infrastructure.database.session import get_db_session
from app.infrastructure.repositories.failure_category_repository import FailureCategoryRepository


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_session(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session


def get_failure_category_repository(
    session: AsyncSession = Depends(get_db_session),
) -> FailureCategoryRepository:
    return FailureCategoryRepository(session)
