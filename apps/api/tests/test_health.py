"""Tests for process health / liveness endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """GET /health must return HTTP 200 with service name and ok status."""
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "recoveryos-api"
    assert "X-Request-ID" in response.headers
