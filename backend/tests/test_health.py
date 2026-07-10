"""Foundation tests for health and root endpoints."""

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError


@pytest.mark.asyncio
async def test_root_metadata(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DevGuard AI API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "devguard-api"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_readiness_when_database_available(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    async def override_session():
        yield mock_db_session

    app = client._transport.app  # type: ignore[attr-defined]
    from app.api.dependencies import get_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_readiness_when_database_unavailable(
    client: AsyncClient,
    mock_db_session: AsyncMock,
) -> None:
    mock_db_session.execute = AsyncMock(
        side_effect=SQLAlchemyError("connection refused"),
    )

    async def override_session():
        yield mock_db_session

    app = client._transport.app  # type: ignore[attr-defined]
    from app.api.dependencies import get_session

    app.dependency_overrides[get_session] = override_session
    try:
        response = await client.get("/api/v1/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    data = response.json()
    assert data["detail"] == "Database is unavailable"
    assert data["error_code"] == "SERVICE_UNAVAILABLE"
    assert "timestamp" in data
    assert data["path"] == "/api/v1/health/ready"
    assert "request_id" in data


@pytest.mark.asyncio
async def test_error_response_includes_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    data = response.json()
    assert "request_id" in data
    assert "error_code" in data
    assert "timestamp" in data
    assert data["path"] == "/api/v1/nonexistent"
    assert "X-Request-ID" in response.headers
