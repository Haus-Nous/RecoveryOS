"""RecoveryOS FastAPI Application Entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import CorrelationIdMiddleware, register_exception_handlers
from app.infrastructure.database import close_database_engine, get_engine
from app.infrastructure.redis import close_redis_client, get_redis_client

logger = get_logger("recoveryos.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown procedures."""
    settings = get_settings()
    configure_logging(log_level=settings.log_level)
    logger.info(f"Starting {settings.app_name} in [{settings.app_env}] environment...")

    # Initialize connection pools
    get_engine()
    get_redis_client()

    yield

    logger.info("Shutting down RecoveryOS API resources...")
    await close_database_engine()
    await close_redis_client()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for RecoveryOS API."""
    settings = get_settings()

    app = FastAPI(
        title="RecoveryOS API",
        description="Payment Reliability & Revenue Recovery Control Plane API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # Middleware
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized exception handlers
    register_exception_handlers(app)

    # Include routes
    app.include_router(api_router)

    return app


app = create_app()
