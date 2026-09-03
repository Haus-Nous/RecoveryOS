"""Pytest fixtures and test environment setup."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# Force test environment variables before importing app
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/recoveryos"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_settings() -> None:
    """Clear settings cache for test isolation."""
    get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client bound to FastAPI application instance."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
