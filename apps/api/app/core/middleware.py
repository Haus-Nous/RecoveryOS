"""HTTP middleware for Correlation IDs and safe centralized error handling."""

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import get_logger

logger = get_logger("recoveryos.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attaches a unique X-Request-ID to every incoming HTTP request and response."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Register safe production-grade exception handlers that avoid leaking stack traces."""

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            f"Unhandled exception on request {request.method} {request.url.path} "
            f"(request_id={request_id}): {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal server error occurred.",
                    "request_id": request_id,
                }
            },
            headers={"X-Request-ID": request_id},
        )
