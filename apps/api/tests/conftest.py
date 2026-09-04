import os
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Force test environment variables before importing app
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/recoveryos_test"
os.environ["SYNC_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/recoveryos_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.infrastructure.persistence.models.base import Base
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_settings() -> None:
    """Clear settings cache for test isolation."""
    get_settings.cache_clear()


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Function-scoped AsyncEngine using NullPool for async event loop isolation."""
    settings = get_settings()
    eng = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
        future=True,
    )
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Function-scoped async session factory."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db_session(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncGenerator[AsyncSession, None]:
    """Isolated database session for tests with automatic cleanup."""
    async with session_factory() as session:
        yield session

    # Cleanup table data after test
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))


@pytest.fixture
def uow_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Factory for SqlAlchemyUnitOfWork."""
    return lambda: SqlAlchemyUnitOfWork(session_factory)


@pytest.fixture
async def seed_merchant(db_session: AsyncSession) -> Any:
    """Fixture to seed a test merchant."""

    async def _seed(
        merchant_id: str = "merch_01JTEST00000000000000000000",
        name: str = "Test Merchant",
        slug: str = "test-merchant",
    ) -> MerchantModel:
        now = datetime.now(UTC)
        merchant = MerchantModel(
            id=merchant_id,
            name=name,
            slug=slug,
            created_at=now,
            updated_at=now,
        )
        db_session.add(merchant)
        await db_session.flush()
        await db_session.commit()
        return merchant

    return _seed


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client bound to FastAPI application instance."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
