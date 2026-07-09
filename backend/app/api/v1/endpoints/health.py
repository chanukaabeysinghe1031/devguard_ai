"""Health check and system status endpoints."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.api.dependencies import get_session, get_settings_dep
from app.core.config import Settings
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Application health check")
async def health_check(settings: Settings = Depends(get_settings_dep)) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        timestamp=datetime.now(UTC),
    )


@router.get("/health/ready", summary="Readiness probe including database connectivity")
async def readiness_check(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected"}
