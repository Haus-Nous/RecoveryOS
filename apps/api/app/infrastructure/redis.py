"""Redis async client management and connectivity verification."""

import asyncio

from redis.asyncio import Redis, from_url

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("recoveryos.infrastructure.redis")

_redis_client: "Redis[str] | None" = None


def get_redis_client() -> "Redis[str]":
    """Get or initialize singleton async Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=2.0,
            socket_connect_timeout=2.0,
        )
    return _redis_client


async def check_redis_connectivity(timeout_seconds: float = 2.0) -> tuple[bool, str | None]:
    """Verify live Redis connectivity via PING/PONG with a strict timeout.

    Returns:
        tuple[bool, str | None]: (is_healthy, error_message)
    """
    try:
        client = get_redis_client()
        async with asyncio.timeout(timeout_seconds):
            pong = await client.ping()
            if bool(pong):
                return True, None
            return False, f"Unexpected Redis ping response: {pong}"
    except TimeoutError:
        return False, f"Redis connectivity check timed out after {timeout_seconds}s"
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return False, str(exc)


async def close_redis_client() -> None:
    """Close Redis client on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed.")
