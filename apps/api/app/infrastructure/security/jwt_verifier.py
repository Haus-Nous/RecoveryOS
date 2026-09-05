"""Asynchronous, standards-based JWT / OIDC token verifier compatible with Supabase Auth."""

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient, PyJWKSet

from app.application.ports.authentication import AuthenticatedPrincipal, TokenVerifier
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger

logger = get_logger("recoveryos.security.jwt")

MAX_TOKEN_BYTES = 8192  # 8 KiB upper bound to prevent resource exhaustion


class JwtTokenVerifier(TokenVerifier):
    """Asynchronous JWT/OIDC verifier supporting ES256 and RS256 with bounded JWKS caching."""

    def __init__(
        self,
        issuer: str | None,
        audience: str | None = "authenticated",
        jwks_url: str | None = None,
        allowed_algorithms: Sequence[str] = ("ES256", "RS256"),
        jwks_cache_ttl_seconds: int = 300,
        clock_skew_seconds: int = 10,
        jwk_client: PyJWKClient | None = None,
        static_keys: dict[str, Any] | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._jwks_url = jwks_url
        self._allowed_algorithms = list(allowed_algorithms)
        self._jwks_cache_ttl_seconds = jwks_cache_ttl_seconds
        self._clock_skew_seconds = clock_skew_seconds

        # Test or injected static JWKs
        self._static_keys = static_keys or {}
        self._jwk_client = jwk_client

        # Dynamic cache
        self._cached_jwk_set: PyJWKSet | None = None
        self._jwk_set_fetched_at: float = 0.0

    async def _fetch_jwks(self) -> PyJWKSet:
        """Fetch JWKS asynchronously with TTL caching."""
        now = time.time()
        if (
            self._cached_jwk_set is not None
            and (now - self._jwk_set_fetched_at) < self._jwks_cache_ttl_seconds
        ):
            return self._cached_jwk_set

        if not self._jwks_url:
            raise AuthenticationError("JWKS URL is not configured.")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
                jwks_data = resp.json()
                self._cached_jwk_set = PyJWKSet.from_dict(jwks_data)
                self._jwk_set_fetched_at = now
                return self._cached_jwk_set
        except Exception as exc:
            logger.error("Failed to fetch JWKS", exc_info=False)
            if self._cached_jwk_set is not None:
                # Return stale cache if available as fallback within reason
                return self._cached_jwk_set
            raise AuthenticationError("Unable to fetch JSON Web Key Set for verification.") from exc

    async def _get_signing_key(self, kid: str | None, alg: str) -> Any:
        """Retrieve signing key by kid with single-refresh retry on unknown kid."""
        if kid and kid in self._static_keys:
            return self._static_keys[kid]

        if self._jwk_client is not None and kid:
            try:
                return self._jwk_client.get_signing_key(kid).key
            except Exception as e:
                raise AuthenticationError(f"Unknown key ID: {kid}") from e

        if not self._jwks_url:
            raise AuthenticationError("No signing keys or JWKS endpoint configured.")

        jwk_set = await self._fetch_jwks()
        try:
            if kid:
                return jwk_set[kid].key
            # If no kid, attempt first matching algorithm
            for jwk in jwk_set.keys:
                if getattr(jwk, "Algorithm", None) == alg:
                    return jwk.key
            raise KeyError(f"No key found for kid={kid}, alg={alg}")
        except KeyError:
            # Refresh JWKS once if unknown kid encountered
            logger.info("Unknown kid encountered; refreshing JWKS cache...")
            self._cached_jwk_set = None
            jwk_set = await self._fetch_jwks()
            try:
                if kid:
                    return jwk_set[kid].key
                raise AuthenticationError(f"Signing key with kid '{kid}' not found in JWKS.")
            except KeyError as err:
                raise AuthenticationError(
                    f"Signing key with kid '{kid}' not found after JWKS refresh."
                ) from err

    async def verify_token(self, token: str) -> AuthenticatedPrincipal:
        """Asynchronously verify JWT signature, standard claims, and return principal."""
        if not token or not isinstance(token, str):
            raise AuthenticationError("Authentication token is missing or malformed.")

        token_bytes = len(token.encode("utf-8"))
        if token_bytes > MAX_TOKEN_BYTES:
            raise AuthenticationError("Authentication token exceeds maximum permitted size.")

        # Inspect unverified header for algorithm and kid
        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception as e:
            raise AuthenticationError("Malformed JWT header.") from e

        alg = unverified_header.get("alg")
        if not alg or alg.upper() == "NONE" or alg not in self._allowed_algorithms:
            raise AuthenticationError(f"Forbidden or unsupported token algorithm: {alg}")

        kid = unverified_header.get("kid")
        signing_key = await self._get_signing_key(kid, alg)

        # Build validation options
        decode_kwargs: dict[str, Any] = {
            "algorithms": [alg],
            "leeway": self._clock_skew_seconds,
            "options": {
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": False,
                "verify_aud": self._audience is not None,
                "verify_iss": self._issuer is not None,
                "require": ["exp", "sub"],
            },
        }
        if self._audience:
            decode_kwargs["audience"] = self._audience
        if self._issuer:
            decode_kwargs["issuer"] = self._issuer

        try:
            payload = jwt.decode(token, signing_key, **decode_kwargs)
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationError("Authentication token has expired.") from e
        except jwt.ImmatureSignatureError as e:
            raise AuthenticationError("Authentication token not valid yet (nbf).") from e
        except jwt.InvalidIssuerError as e:
            raise AuthenticationError("Token issuer mismatch.") from e
        except jwt.InvalidAudienceError as e:
            raise AuthenticationError("Token audience mismatch.") from e
        except jwt.InvalidSignatureError as e:
            raise AuthenticationError("Invalid cryptographic signature.") from e
        except jwt.PyJWTError as e:
            raise AuthenticationError(f"Token validation failed: {e!s}") from e

        sub = payload.get("sub")
        if not sub or not isinstance(sub, str) or not sub.strip():
            raise AuthenticationError("Token payload missing required 'sub' claim.")

        # Extract standard claims
        iss = payload.get("iss") or self._issuer or "unknown_issuer"
        email = payload.get("email")
        email_verified = payload.get("email_verified")
        iat_raw = payload.get("iat")
        issued_at = (
            datetime.fromtimestamp(iat_raw, tz=UTC)
            if iat_raw and isinstance(iat_raw, (int, float))
            else None
        )

        return AuthenticatedPrincipal(
            issuer=str(iss),
            subject=str(sub),
            email=str(email) if email else None,
            email_verified=bool(email_verified) if email_verified is not None else None,
            issued_at=issued_at,
        )
