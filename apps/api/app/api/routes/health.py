"""Process health and infrastructure dependency readiness endpoints."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.infrastructure.database import check_database_connectivity
from app.infrastructure.redis import check_redis_connectivity

router = APIRouter(tags=["Health & Readiness"])


class HealthResponse(BaseModel):
    """Process liveness response model."""

    status: str = Field(default="ok", description="Process health state")
    service: str = Field(default="recoveryos-api", description="Service identifier")


class DependenciesStatus(BaseModel):
    """Readiness status for external backing infrastructure."""

    postgres: str = Field(description="PostgreSQL connectivity status")
    redis: str = Field(description="Redis connectivity status")


class ReadinessResponse(BaseModel):
    """Comprehensive dependency readiness response model."""

    status: str = Field(description="'ready' when all dependencies are healthy, else 'not_ready'")
    service: str = Field(default="recoveryos-api", description="Service identifier")
    dependencies: DependenciesStatus
    errors: list[str] = Field(default_factory=list, description="Any connectivity errors")


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Health / Liveness Check",
    description="Returns HTTP 200 if the API process is alive and responding.",
)
async def get_health() -> HealthResponse:
    """Return process liveness state."""
    return HealthResponse(status="ok", service="recoveryos-api")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "All infrastructure dependencies are connected and healthy."},
        503: {"description": "One or more infrastructure dependencies are unavailable."},
    },
    summary="Infrastructure Readiness Check",
    description="Performs active connectivity checks on PostgreSQL and Redis.",
)
async def get_readiness(response: Response) -> ReadinessResponse:
    """Check connectivity to PostgreSQL and Redis.

    Returns HTTP 200 when all dependencies are healthy, or HTTP 503 when any dependency fails.
    """
    pg_ok, pg_err = await check_database_connectivity()
    redis_ok, redis_err = await check_redis_connectivity()

    errors: list[str] = []
    if not pg_ok and pg_err:
        errors.append(f"PostgreSQL: {pg_err}")
    if not redis_ok and redis_err:
        errors.append(f"Redis: {redis_err}")

    is_all_ready = pg_ok and redis_ok

    if not is_all_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if is_all_ready else "not_ready",
        service="recoveryos-api",
        dependencies=DependenciesStatus(
            postgres="connected" if pg_ok else "disconnected",
            redis="connected" if redis_ok else "disconnected",
        ),
        errors=errors,
    )
