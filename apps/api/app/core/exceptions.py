"""Domain and application exceptions for RecoveryOS."""


class RecoveryOSError(Exception):
    """Base exception for all RecoveryOS errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConcurrencyError(RecoveryOSError):
    """Raised when an optimistic concurrency check fails."""


class EntityNotFoundError(RecoveryOSError):
    """Raised when an expected entity does not exist."""


class DuplicateEntityError(RecoveryOSError):
    """Raised when attempting to create an entity that already exists."""


class AuthenticationError(RecoveryOSError):
    """Raised when authentication credentials (e.g. JWT) are invalid, expired, or missing."""


class AuthorizationError(RecoveryOSError):
    """Raised when an authenticated principal lacks required merchant membership or permission."""


class LastOwnerViolationError(AuthorizationError):
    """Raised when an operation would leave a merchant without an ACTIVE owner."""
