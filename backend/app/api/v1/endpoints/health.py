"""Health check endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session, get_settings_dep
from app.core.config import Settings
from app.core.exceptions import build_error_response

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness probe")
async def liveness(settings: Settings = Depends(get_settings_dep)) -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.app_version,
    }


@router.get("/health/ready", summary="Readiness probe with database connectivity check")
async def readiness(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return build_error_response(
            request,
            detail="Database is unavailable",
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
        )
    except Exception:
        return build_error_response(
            request,
            detail="Database is unavailable",
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
        )

    return {"status": "ready", "database": "connected"}
