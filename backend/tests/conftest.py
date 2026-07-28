"""Pytest configuration and fixtures."""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytest_plugins = ["tests.conftest_db"]

os.environ.setdefault("PROJECT_NAME", "DevGuard AI")
os.environ.setdefault("APP_VERSION", "1.0.0")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://devguard:change_me@localhost:5432/devguard",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-jwt-secret-key-with-at-least-32-characters",
)
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("FILE_STORAGE_BACKEND", "local")
os.environ.setdefault(
    "FILE_STORAGE_PATH",
    str(__import__("pathlib").Path(__file__).resolve().parent / ".test_uploads"),
)
os.environ.setdefault("MAX_UPLOAD_SIZE_BYTES", "1048576")
os.environ.setdefault("MAX_FILES_PER_UPLOAD", "5")
os.environ.setdefault("ENABLE_RAG", "false")
os.environ.setdefault("ENABLE_LLM", "false")
os.environ.setdefault("ANALYSIS_EXECUTION_MODE", "sync")
os.environ.setdefault("RAG_BACKEND", "memory")
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("LLM_PROVIDER", "local")
os.environ.setdefault(
    "KNOWLEDGE_BASE_PATH",
    str(__import__("pathlib").Path(__file__).resolve().parents[2] / "knowledge_base"),
)
os.environ.setdefault("DEFAULT_EXECUTION_MODE", "rag_llm")
os.environ.setdefault("DEFAULT_LATENCY_LIMIT_MS", "30000")
os.environ.setdefault("ENABLE_CONFIDENCE_ROUTING", "true")
os.environ.setdefault("ENABLE_LOCAL_REASONER", "true")
os.environ.setdefault("ENABLE_EXTERNAL_LLM", "false")
os.environ.setdefault("DEFAULT_RETRIEVAL_MODE", "hybrid_static")
os.environ.setdefault("ENABLE_HYBRID_RETRIEVAL", "true")
os.environ.setdefault("ENABLE_HISTORICAL_RETRIEVAL", "false")
os.environ.setdefault("ENABLE_LEXICAL_RETRIEVAL", "true")
os.environ.setdefault("ENABLE_STACK_TRACE_SIMILARITY", "true")
os.environ.setdefault("ENABLE_RETRIEVAL_DIVERSITY", "true")
os.environ.setdefault("HYBRID_WEIGHT_PROFILE", "hybrid_static_v1")

from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(repository_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client bound to the isolated test database session."""
    from app.api.dependencies import get_session
    from app.infrastructure.database.seed import seed_failure_categories

    # Analysis persistence requires the 11 approved failure categories.
    await seed_failure_categories(repository_db_session)
    await repository_db_session.commit()

    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield repository_db_session
            await repository_db_session.commit()
        except Exception:
            await repository_db_session.rollback()
            raise

    app.dependency_overrides[get_session] = _override_session
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    result = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session
