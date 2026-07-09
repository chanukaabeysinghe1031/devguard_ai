"""DevGuard AI — FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import DevGuardError, devguard_exception_handler, http_exception_handler
from app.core.logging import setup_logging, get_logger
from app.infrastructure.database.seed import seed_failure_categories
from app.infrastructure.database.session import close_db, get_db_session, init_db
from fastapi import HTTPException

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    logger.info("application_starting", env=settings.app_env, version=__version__)

    try:
        init_db(settings)
        async for session in get_db_session():
            created = await seed_failure_categories(session)
            if created:
                logger.info("seeded_failure_categories", count=created)
            break
    except Exception as exc:
        logger.warning("database_initialization_skipped", error=str(exc))

    yield

    try:
        await close_db()
    except Exception:
        pass
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-Powered DevOps Intelligence Platform — analyse CI/CD failures, extract evidence, and generate remediation recommendations.",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DevGuardError, devguard_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": __version__,
            "docs": "/docs",
            "api": settings.api_v1_prefix,
        }

    return app


app = create_app()
