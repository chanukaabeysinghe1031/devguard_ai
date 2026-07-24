"""Alembic migration integrity tests (isolated migration test database).

Uses a database separate from ``devguard_test`` (the one shared by the
repository/seed fixtures in ``conftest_db.py``) so that downgrade/upgrade
round-tripping never disturbs state other tests depend on.
"""

from __future__ import annotations

import asyncio
import os

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.conftest_db import (
    ALL_APPLICATION_TABLES,
    run_alembic_downgrade,
    run_alembic_upgrade,
)

MIGRATION_TEST_DATABASE_NAME = os.environ.get(
    "MIGRATION_TEST_POSTGRES_DB", "devguard_test_migrations"
)
MIGRATION_TEST_DATABASE_URL = os.environ.get(
    "MIGRATION_TEST_DATABASE_URL",
    (
        f"postgresql+asyncpg://{os.environ.get('POSTGRES_USER', 'devguard')}:"
        f"{os.environ.get('POSTGRES_PASSWORD', 'change_me')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/"
        f"{MIGRATION_TEST_DATABASE_NAME}"
    ),
)

EXPECTED_TABLES = frozenset(ALL_APPLICATION_TABLES)

# Key tables explicitly called out by the schema evolution ADR-012 that must
# exist post-Migration-007.
KEY_TABLES = frozenset(
    {
        "organizations",
        "organization_members",
        "projects",
        "incidents",
        "analysis_runs",
        "recommendation_steps",
        "knowledge_documents",
        "knowledge_chunks",
    }
)


async def _drop_and_recreate_migration_database() -> None:
    conn = await asyncpg.connect(
        user=os.environ.get("POSTGRES_USER", "devguard"),
        password=os.environ.get("POSTGRES_PASSWORD", "change_me"),
        database="postgres",
        host=os.environ.get("POSTGRES_HOST", "localhost"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{MIGRATION_TEST_DATABASE_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{MIGRATION_TEST_DATABASE_NAME}"')
    finally:
        await conn.close()


@pytest.fixture(scope="module")
def migration_database_url() -> str:
    try:
        asyncio.run(_drop_and_recreate_migration_database())
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Migration test database unavailable: {exc}")
    return MIGRATION_TEST_DATABASE_URL


async def _fetch_table_names(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
            return {row[0] for row in result.all()}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_alembic_upgrade_head_from_base(migration_database_url: str) -> None:
    """A freshly created (base) database must reach the full target schema."""
    run_alembic_upgrade(migration_database_url, "head")

    tables = await _fetch_table_names(migration_database_url)

    assert KEY_TABLES.issubset(tables)
    assert EXPECTED_TABLES.issubset(tables)
    assert "analysis_history" not in tables


@pytest.mark.asyncio
async def test_alembic_downgrade_to_base_then_upgrade(migration_database_url: str) -> None:
    """The full migration chain must be reversible and safely re-appliable."""
    # Depends on test_alembic_upgrade_head_from_base having already run in
    # this module, leaving the database at head.
    run_alembic_downgrade(migration_database_url, "base")

    tables_after_downgrade = await _fetch_table_names(migration_database_url)
    assert "organizations" not in tables_after_downgrade
    assert "incidents" not in tables_after_downgrade

    run_alembic_upgrade(migration_database_url, "head")

    tables_after_reupgrade = await _fetch_table_names(migration_database_url)
    assert KEY_TABLES.issubset(tables_after_reupgrade)
    assert "analysis_history" not in tables_after_reupgrade
