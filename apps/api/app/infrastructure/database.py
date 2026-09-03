"""SQLAlchemy 2.x async engine, session lifecycle, and connectivity verification."""

import asyncio
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("recoveryos.infrastructure.database")

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create singleton async SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=False,
            future=True,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or initialize the async session factory."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency providing an async database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def check_database_connectivity(timeout_seconds: float = 2.0) -> tuple[bool, str | None]:
    """Verify live PostgreSQL connectivity via `SELECT 1` with a strict timeout.

    Returns:
        tuple[bool, str | None]: (is_healthy, error_message)
    """
    try:
        engine = get_engine()
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                scalar = result.scalar()
                if scalar == 1:
                    return True, None
                return False, f"Unexpected DB query result: {scalar}"
    except TimeoutError:
        return False, f"Database connectivity check timed out after {timeout_seconds}s"
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return False, str(exc)


async def close_database_engine() -> None:
    """Close SQLAlchemy async engine on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database engine disposed.")
