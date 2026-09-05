"""Authentication ports and domain abstractions for external identity verification.

CRITICAL INVARIANTS:
1. AuthenticatedPrincipal is purely provider-independent.
2. JWT role/merchant/permission claims are NEVER trusted for RecoveryOS authorization.
3. Verification is strictly asynchronous to avoid blocking the event loop.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Immutable, provider-independent representation of an authenticated external identity."""

    issuer: str
    subject: str
    email: str | None = None
    email_verified: bool | None = None
    issued_at: datetime | None = None


class TokenVerifier(Protocol):
    """Port for verifying external identity tokens."""

    async def verify_token(self, token: str) -> AuthenticatedPrincipal:
        """Asynchronously verify token cryptographic signature, claims, and return principal.

        Raises:
            AuthenticationError: If token is invalid, expired, malformed, or untrusted.
        """
        ...
