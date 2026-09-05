"""Typed provider error hierarchy for RecoveryOS provider boundary."""

from typing import Any


class ProviderError(Exception):
    """Base exception for all payment provider errors."""

    def __init__(
        self,
        message: str,
        *,
        is_transient: bool = False,
        provider: str | None = None,
        raw_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.is_transient = is_transient
        self.provider = provider
        self.raw_error = raw_error or {}


class ProviderAuthenticationError(ProviderError):
    """Authentication or credential failure with payment provider (HTTP 401 or 400 auth errors)."""

    def __init__(self, message: str = "Provider authentication failed", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderAuthorizationError(ProviderError):
    """Authorization failure (e.g. HTTP 403 Forbidden)."""

    def __init__(self, message: str = "Provider authorization failed", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderRateLimitError(ProviderError):
    """Provider API rate limit / 429 backpressure."""

    def __init__(
        self,
        message: str = "Provider rate limit exceeded",
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, is_transient=True, **kwargs)
        self.retry_after = retry_after


class ProviderTimeoutError(ProviderError):
    """Provider network connect or read timeout."""

    def __init__(self, message: str = "Provider request timed out", **kwargs: Any) -> None:
        super().__init__(message, is_transient=True, **kwargs)


class ProviderNetworkError(ProviderError):
    """Provider low-level network connection or socket error."""

    def __init__(self, message: str = "Provider network connection error", **kwargs: Any) -> None:
        super().__init__(message, is_transient=True, **kwargs)


class ProviderUnavailableError(ProviderError):
    """Provider service unavailable or server error (HTTP 500, 502, 503, 504)."""

    def __init__(
        self,
        message: str = "Provider service unavailable",
        *,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, is_transient=True, **kwargs)
        self.status_code = status_code


class ProviderBadRequestError(ProviderError):
    """Provider rejected request parameters or input validation failed."""

    def __init__(self, message: str = "Provider bad request", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderValidationError(ProviderBadRequestError):
    """Provider rejected request due to field validation error."""

    def __init__(self, message: str = "Provider validation error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ProviderNotFoundError(ProviderError):
    """Requested provider resource was not found (HTTP 404)."""

    def __init__(self, message: str = "Provider resource not found", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderMalformedResponseError(ProviderError):
    """Provider response could not be parsed or was missing critical identifiers/money fields."""

    def __init__(self, message: str = "Malformed provider response", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderResponseTooLargeError(ProviderError):
    """Provider response exceeded maximum allowed byte size during streamed consumption."""

    def __init__(
        self, message: str = "Provider response exceeded maximum size limit", **kwargs: Any
    ) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderAmbiguousWriteError(ProviderError):
    """Provider write request (POST /orders) timed out or failed ambiguously.

    Crucial invariant: The write may or may not have committed at the provider.
    It must NOT be blindly retried.
    """

    def __init__(
        self,
        message: str = "Provider write state is ambiguous; write may or may not have committed",
        *,
        receipt: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, is_transient=False, **kwargs)
        self.receipt = receipt


class ProviderAmbiguityError(ProviderError):
    """Multiple provider entities matched a single correlation reference, indicating an upstream integrity error."""

    def __init__(
        self,
        message: str = "Multiple provider records matched correlation lookup",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderUnsupportedCurrencyError(ProviderError):
    """Provider currency is unsupported or invalid."""

    def __init__(self, message: str = "Unsupported provider currency", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderLiveModeForbiddenError(ProviderError):
    """Attempted to execute in LIVE mode, which is strictly prohibited in Phase 5."""

    def __init__(
        self,
        message: str = "Live mode is strictly forbidden in Phase 5; only TEST mode is allowed",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderInvalidKeyFormatError(ProviderError):
    """Provider credential key format is invalid or inconsistent with environment mode."""

    def __init__(self, message: str = "Invalid provider key format", **kwargs: Any) -> None:
        super().__init__(message, is_transient=False, **kwargs)


class ProviderCredentialResolutionError(ProviderError):
    """Failed to resolve provider credentials from alias or alias not allowlisted."""

    def __init__(
        self, message: str = "Provider credential resolution failed", **kwargs: Any
    ) -> None:
        super().__init__(message, is_transient=False, **kwargs)
