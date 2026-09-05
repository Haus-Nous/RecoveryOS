"""Managed HTTP transport client for Razorpay API with strict safety invariants."""

import asyncio
import email.utils
import json
import logging
import time
from typing import Any

import httpx

from app.application.ports.provider_credentials import ProviderCredentials
from app.providers.errors import (
    ProviderAmbiguousWriteError,
    ProviderAuthenticationError,
    ProviderAuthorizationError,
    ProviderBadRequestError,
    ProviderError,
    ProviderLiveModeForbiddenError,
    ProviderMalformedResponseError,
    ProviderNotFoundError,
    ProviderRateLimitError,
    ProviderResponseTooLargeError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderValidationError,
)

logger = logging.getLogger("app.providers.razorpay.client")

OFFICIAL_RAZORPAY_BASE_URL = "https://api.razorpay.com"
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB
MAX_PROVIDER_RESPONSE_BYTES = DEFAULT_MAX_RESPONSE_BYTES
MAX_RETRY_AFTER_SECONDS = 5.0
DEFAULT_MAX_GET_ATTEMPTS = 3


class RazorpayHttpClient:
    """Hardened HTTP client communicating with Razorpay REST API in Test Mode."""

    def __init__(
        self,
        credentials: ProviderCredentials,
        *,
        base_url: str = OFFICIAL_RAZORPAY_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        connect_timeout: float = 5.0,
        read_timeout: float = 10.0,
        write_timeout: float = 10.0,
        pool_timeout: float = 5.0,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_get_attempts: int = DEFAULT_MAX_GET_ATTEMPTS,
        max_retries: int | None = None,
        backoff_base_seconds: float = 0.1,
        verify: bool = True,
    ) -> None:
        if credentials.key_id.startswith("rzp_live_"):
            raise ProviderLiveModeForbiddenError(
                f"Live Razorpay Key ID prefix 'rzp_live_' detected: {credentials.key_id[:12]}... "
                "Phase 5 strictly prohibits live keys. Request failed closed."
            )

        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._max_response_bytes = max_response_bytes
        self._max_get_attempts = max_retries if max_retries is not None else max_get_attempts
        self._backoff_base_seconds = backoff_base_seconds
        self.verify = verify

        self._timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )
        self._auth = httpx.BasicAuth(
            username=credentials.key_id,
            password=credentials.key_secret.get_secret_value(),
        )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=self._auth,
            timeout=self._timeout,
            follow_redirects=False,  # Invariant: Never follow redirects
            verify=verify,  # Invariant: Strict TLS verification
            transport=transport,
        )

    async def close(self) -> None:
        """Close underlying HTTP client session."""
        await self._client.aclose()

    async def __aenter__(self) -> "RazorpayHttpClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a safe, idempotent GET request with bounded retries for transient errors."""
        attempt = 0
        backoff = self._backoff_base_seconds

        while True:
            attempt += 1
            start_time = time.perf_counter()
            try:
                request = self._client.build_request("GET", path, params=params)
                # Ensure no secrets leak in log
                logger.debug(
                    "Executing provider request",
                    extra={
                        "provider": "RAZORPAY",
                        "method": "GET",
                        "path": path,
                        "attempt": attempt,
                    },
                )
                response = await self._client.send(request, stream=True)
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                # Check if retryable transient error
                status = response.status_code
                if status in (502, 503, 504) and attempt < self._max_get_attempts:
                    await response.aclose()
                    logger.warning(
                        "Transient provider gateway error received; retrying",
                        extra={"status_code": status, "attempt": attempt, "elapsed_ms": elapsed_ms},
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                if status == 429:
                    retry_after_sec = self._parse_retry_after(response.headers.get("Retry-After"))
                    await response.aclose()
                    if attempt < self._max_get_attempts:
                        wait_sec = min(retry_after_sec or backoff, MAX_RETRY_AFTER_SECONDS)
                        logger.warning(
                            "Provider rate limit (429) received; backing off",
                            extra={"attempt": attempt, "wait_sec": wait_sec},
                        )
                        await asyncio.sleep(wait_sec)
                        backoff *= 2
                        continue
                    else:
                        raise ProviderRateLimitError(
                            "Provider rate limit exceeded after maximum retry attempts",
                            retry_after=retry_after_sec,
                        )

                # Consume streamed response with strict byte limiting
                body_bytes = await self._consume_streamed_body(response)
                await response.aclose()

                return self._parse_and_handle_response(status, body_bytes)

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
                if attempt < self._max_get_attempts:
                    logger.warning(
                        "Transient network error on provider GET; retrying",
                        extra={"error": str(exc), "attempt": attempt},
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise ProviderTimeoutError(
                    f"Provider request timed out after {attempt} attempts: {exc}"
                ) from exc

    async def post(
        self,
        path: str,
        json_data: dict[str, Any],
        *,
        receipt: str | None = None,
    ) -> dict[str, Any]:
        """Execute a write request (POST) with strict NO-BLIND-RETRY semantics."""
        start_time = time.perf_counter()
        request = self._client.build_request("POST", path, json=json_data)
        logger.debug(
            "Executing provider write request",
            extra={"provider": "RAZORPAY", "method": "POST", "path": path},
        )

        try:
            response = await self._client.send(request, stream=True)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            # CRITICAL: Do NOT retry blindly. State at provider is ambiguous.
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Ambiguous write failure on POST request; write may or may not have committed",
                extra={
                    "provider": "RAZORPAY",
                    "path": path,
                    "receipt": receipt,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise ProviderAmbiguousWriteError(
                f"Network error during POST {path}; write state is ambiguous",
                receipt=receipt,
            ) from exc

        status = response.status_code
        body_bytes = await self._consume_streamed_body(response)
        await response.aclose()

        return self._parse_and_handle_response(status, body_bytes)

    async def _consume_streamed_body(self, response: httpx.Response) -> bytes:
        """Stream response body chunks incrementally enforcing MAX_PROVIDER_RESPONSE_BYTES."""
        # 1. Early Content-Length check if present
        content_length_header = response.headers.get("Content-Length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
                if content_length > self._max_response_bytes:
                    await response.aclose()
                    raise ProviderResponseTooLargeError(
                        f"Response Content-Length {content_length} exceeds limit {self._max_response_bytes}"
                    )
            except ValueError:
                pass  # Ignore unparseable Content-Length; fallback to stream counting

        # 2. Incremental byte counting during stream consumption
        accumulated = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=8192):
            accumulated.extend(chunk)
            if len(accumulated) > self._max_response_bytes:
                await response.aclose()
                raise ProviderResponseTooLargeError(
                    f"Response streamed bytes exceeded maximum allowed limit of {self._max_response_bytes} bytes"
                )

        return bytes(accumulated)

    def _parse_and_handle_response(self, status: int, body_bytes: bytes) -> dict[str, Any]:
        """Parse validated JSON body and map status codes to typed exceptions."""
        try:
            data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception as exc:
            if status >= 400:
                raise ProviderUnavailableError(
                    f"Provider returned HTTP {status} with unparseable body",
                    status_code=status,
                ) from exc
            raise ProviderMalformedResponseError(f"Failed to parse JSON response: {exc}") from exc

        if not isinstance(data, dict):
            raise ProviderMalformedResponseError(
                f"Expected JSON object response, got {type(data).__name__}"
            )

        if status < 400:
            return data

        # Error response handling
        error_payload = data.get("error", {})
        if not isinstance(error_payload, dict):
            error_payload = {}

        error_code = str(error_payload.get("code", "")).upper()
        error_desc = str(error_payload.get("description", ""))
        error_reason = str(error_payload.get("reason", "")).lower()

        # Check for authentication failures (both 401 and 400 with credential-specific errors)
        is_auth_failure = (
            status == 401
            or "unauthorized" in error_code.lower()
            or "auth" in error_code.lower()
            or "invalid key" in error_desc.lower()
            or "authentication failed" in error_desc.lower()
            or error_reason
            in ("auth_failed", "invalid_credentials", "bad_request_error_unauthorized")
        )

        if is_auth_failure:
            raise ProviderAuthenticationError(
                f"Provider authentication failed: {error_desc or error_code or 'Invalid credentials'}",
                raw_error=error_payload,
            )

        if status == 403:
            raise ProviderAuthorizationError(
                f"Provider authorization failed: {error_desc or error_code}",
                raw_error=error_payload,
            )

        if status == 404:
            raise ProviderNotFoundError(
                f"Provider resource not found: {error_desc or error_code}",
                raw_error=error_payload,
            )

        if status in (500, 502, 503, 504):
            raise ProviderUnavailableError(
                f"Provider service unavailable (HTTP {status}): {error_desc or error_code}",
                status_code=status,
                raw_error=error_payload,
            )

        if status == 400:
            if (
                error_payload.get("field")
                or "required" in error_desc.lower()
                or "invalid" in error_desc.lower()
                or "validation" in error_desc.lower()
                or "amount" in error_desc.lower()
            ):
                raise ProviderValidationError(
                    f"Provider validation failed (HTTP 400): {error_desc or error_code}",
                    raw_error=error_payload,
                )
            raise ProviderBadRequestError(
                f"Provider bad request (HTTP 400): {error_desc or error_code}",
                raw_error=error_payload,
            )

        raise ProviderError(
            f"Provider returned unhandled HTTP {status}: {error_desc or error_code}",
            raw_error=error_payload,
        )

    def _parse_retry_after(self, header_val: str | None) -> float | None:
        """Parse Retry-After header as numeric seconds or HTTP-date, bounded by MAX_RETRY_AFTER_SECONDS."""
        if not header_val or not header_val.strip():
            return None

        val = header_val.strip()
        # 1. Check if integer / float seconds
        try:
            seconds = float(val)
            if seconds < 0:
                return None
            return min(seconds, MAX_RETRY_AFTER_SECONDS)
        except ValueError:
            pass

        # 2. Check if HTTP-date format
        try:
            parsed_time = email.utils.parsedate_to_datetime(val)
            now = time.time()
            diff = parsed_time.timestamp() - now
            if diff < 0:
                return None
            return min(diff, MAX_RETRY_AFTER_SECONDS)
        except Exception:
            return None
