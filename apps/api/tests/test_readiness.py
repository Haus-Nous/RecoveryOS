"""Tests for infrastructure dependency readiness endpoint."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_readiness_all_healthy(client: AsyncClient) -> None:
    """GET /ready returns HTTP 200 when Postgres and Redis connectivity checks succeed."""
    with (
        patch(
            "app.api.routes.health.check_database_connectivity",
            return_value=(True, None),
        ),
        patch(
            "app.api.routes.health.check_redis_connectivity",
            return_value=(True, None),
        ),
    ):
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "recoveryos-api"
        assert data["dependencies"]["postgres"] == "connected"
        assert data["dependencies"]["redis"] == "connected"
        assert data["errors"] == []


@pytest.mark.asyncio
async def test_readiness_postgres_failure(client: AsyncClient) -> None:
    """GET /ready returns HTTP 503 when Postgres connectivity fails."""
    with (
        patch(
            "app.api.routes.health.check_database_connectivity",
            return_value=(False, "Connection refused"),
        ),
        patch(
            "app.api.routes.health.check_redis_connectivity",
            return_value=(True, None),
        ),
    ):
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["postgres"] == "disconnected"
        assert data["dependencies"]["redis"] == "connected"
        assert any("PostgreSQL: Connection refused" in err for err in data["errors"])


@pytest.mark.asyncio
async def test_readiness_redis_failure(client: AsyncClient) -> None:
    """GET /ready returns HTTP 503 when Redis connectivity fails."""
    with (
        patch(
            "app.api.routes.health.check_database_connectivity",
            return_value=(True, None),
        ),
        patch(
            "app.api.routes.health.check_redis_connectivity",
            return_value=(False, "Connection timeout"),
        ),
    ):
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["postgres"] == "connected"
        assert data["dependencies"]["redis"] == "disconnected"
        assert any("Redis: Connection timeout" in err for err in data["errors"])


@pytest.mark.asyncio
async def test_readiness_all_failing(client: AsyncClient) -> None:
    """GET /ready returns HTTP 503 when both Postgres and Redis fail."""
    with (
        patch(
            "app.api.routes.health.check_database_connectivity",
            return_value=(False, "DB down"),
        ),
        patch(
            "app.api.routes.health.check_redis_connectivity",
            return_value=(False, "Redis down"),
        ),
    ):
        response = await client.get("/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["dependencies"]["postgres"] == "disconnected"
        assert data["dependencies"]["redis"] == "disconnected"
        assert len(data["errors"]) == 2
