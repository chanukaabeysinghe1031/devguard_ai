"""DevGuard AI — FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    DevGuardError,
    devguard_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestIDMiddleware
from app.infrastructure.database.session import close_db, init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)
    config_problems = settings.validate_for_runtime()
    if config_problems:
        logger.warning("configuration_warnings", problems=config_problems)
    init_db(settings)
    logger.info(
        "application_starting",
        environment=settings.environment,
        version=settings.app_version,
    )
    yield
    await close_db()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=f"{settings.project_name} API",
        description="AI-Powered DevOps Intelligence Platform",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(DevGuardError, devguard_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        return {
            "name": "DevGuard AI API",
            "version": settings.app_version,
            "status": "running",
        }

    return app


app = create_app()
