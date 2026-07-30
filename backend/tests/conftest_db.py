"""Database test fixtures for isolated PostgreSQL integration tests."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.core.config import Settings, get_settings
from app.infrastructure.database.session import close_db, ensure_session_factory, init_db

TEST_DATABASE_NAME = os.environ.get("TEST_POSTGRES_DB", "devguard_test")
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    (
        f"postgresql+asyncpg://{os.environ.get('POSTGRES_USER', 'devguard')}:"
        f"{os.environ.get('POSTGRES_PASSWORD', 'change_me')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{TEST_DATABASE_NAME}"
    ),
)

BACKEND_DIR = Path(__file__).resolve().parent.parent

# All application tables registered in app.infrastructure.database.models.
# `analysis_history` is deliberately absent — deprecated by ADR-012.
ALL_APPLICATION_TABLES: tuple[str, ...] = (
    "webhook_deliveries",
    "github_repository_connections",
    "github_installations",
    "audit_logs",
    "feedback",
    "notifications",
    "incident_reports",
    "incident_resolutions",
    "incident_assignments",
    "incident_notes",
    "incident_events",
    "retrieved_documents",
    "recommendation_steps",
    "recommendations",
    "refresh_tokens",
    "evidence_items",
    "predictions",
    "analysis_runs",
    "uploaded_files",
    "incidents",
    "pipeline_runs",
    "project_integrations",
    "projects",
    "organization_members",
    "organizations",
    "knowledge_chunks",
    "knowledge_documents",
    "evaluations",
    "model_versions",
    "failure_categories",
    "users",
)

TEST_TRUNCATE_TABLES = (
    f"TRUNCATE TABLE {', '.join(ALL_APPLICATION_TABLES)} RESTART IDENTITY CASCADE"
)


async def ensure_database_exists(database_name: str) -> None:
    """Create ``database_name`` on the target PostgreSQL server if missing."""
    conn = await asyncpg.connect(
        user=os.environ.get("POSTGRES_USER", "devguard"),
        password=os.environ.get("POSTGRES_PASSWORD", "change_me"),
        database="postgres",
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            database_name,
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await conn.close()


async def _ensure_test_database_exists() -> None:
    await ensure_database_exists(TEST_DATABASE_NAME)


def run_alembic_upgrade(database_url: str, revision: str = "head") -> None:
    """Run ``alembic upgrade <revision>`` against ``database_url``."""
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        command.upgrade(alembic_cfg, revision)
    finally:
        if original_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_url
        get_settings.cache_clear()


def run_alembic_downgrade(database_url: str, revision: str = "base") -> None:
    """Run ``alembic downgrade <revision>`` against ``database_url``."""
    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    original_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        command.downgrade(alembic_cfg, revision)
    finally:
        if original_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_url
        get_settings.cache_clear()


def _run_alembic_upgrade(database_url: str) -> None:
    """Backward-compatible alias for the session-scoped fixture below."""
    run_alembic_upgrade(database_url, "head")


def _test_settings(database_url: str) -> Settings:
    return Settings(
        PROJECT_NAME="DevGuard AI Test",
        APP_VERSION="1.0.0",
        ENVIRONMENT="development",
        DEBUG=False,
        DATABASE_URL=database_url,
    )


@pytest.fixture(scope="session")
def migrated_test_database() -> str:
    try:
        import asyncio

        asyncio.run(_ensure_test_database_exists())
        _run_alembic_upgrade(TEST_DATABASE_URL)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Test database unavailable: {exc}")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_test_database: str) -> AsyncGenerator[AsyncSession, None]:
    init_db(_test_settings(migrated_test_database))
    session_factory = ensure_session_factory()

    async with session_factory() as session:
        await session.execute(text(TEST_TRUNCATE_TABLES))
        await session.commit()
        yield session

    await close_db()


@pytest.fixture
async def repository_db_session(
    migrated_test_database: str,
) -> AsyncGenerator[AsyncSession, None]:
    init_db(_test_settings(migrated_test_database))
    session_factory = ensure_session_factory()

    async with session_factory() as session:
        await session.execute(text(TEST_TRUNCATE_TABLES))
        await session.commit()
        yield session

    await close_db()
