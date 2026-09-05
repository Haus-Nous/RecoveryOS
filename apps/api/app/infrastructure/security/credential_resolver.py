"""Environment-backed provider credential resolver with allowlist enforcement."""

import os
import re

from pydantic import SecretStr

from app.application.ports.provider_credentials import (
    ProviderCredentialResolver,
    ProviderCredentials,
)
from app.providers.errors import (
    ProviderCredentialResolutionError,
    ProviderInvalidKeyFormatError,
    ProviderLiveModeForbiddenError,
)
from app.providers.types import PaymentProviderConnection, ProviderMode

# Default server-controlled allowlist mapping aliases to specific environment variables
DEFAULT_CREDENTIAL_ALLOWLIST: dict[str, tuple[str, str]] = {
    "RAZORPAY_TEST_DEMO": ("RAZORPAY_TEST_DEMO_KEY_ID", "RAZORPAY_TEST_DEMO_KEY_SECRET"),
    "RAZORPAY_TEST_STAGING": ("RAZORPAY_TEST_STAGING_KEY_ID", "RAZORPAY_TEST_STAGING_KEY_SECRET"),
}

ALIAS_REGEX = re.compile(r"^[A-Z0-9_]{3,64}$")


class EnvProviderCredentialResolver(ProviderCredentialResolver):
    """Secure credential resolver extracting provider keys from allowlisted environment variables."""

    def __init__(
        self,
        allowlist: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self._allowlist = allowlist if allowlist is not None else dict(DEFAULT_CREDENTIAL_ALLOWLIST)

    def is_allowlisted(self, credential_ref: str) -> bool:
        """Check whether credential_ref exists in server allowlist and conforms to alias syntax."""
        return bool(ALIAS_REGEX.match(credential_ref)) and credential_ref in self._allowlist

    async def resolve(self, connection: PaymentProviderConnection) -> ProviderCredentials:
        """Resolve ephemeral credentials for connection with strict allowlist and test mode enforcement."""
        # 1. Hard block LIVE mode
        if connection.mode == ProviderMode.LIVE:
            raise ProviderLiveModeForbiddenError(
                "Live mode execution is strictly prohibited in Phase 5; connection mode must be TEST"
            )

        # 2. Strict syntax validation
        if not ALIAS_REGEX.match(connection.credential_ref):
            raise ProviderCredentialResolutionError(
                f"Invalid credential_ref syntax: '{connection.credential_ref}'. "
                "Must match ^[A-Z0-9_]{3,64}$ with no traversal characters or punctuation."
            )

        # 3. Server-controlled allowlist validation
        if connection.credential_ref not in self._allowlist:
            raise ProviderCredentialResolutionError(
                f"Credential alias '{connection.credential_ref}' is not registered in server allowlist. "
                "Arbitrary environment variable derivation is blocked."
            )

        key_id_var, key_secret_var = self._allowlist[connection.credential_ref]

        raw_key_id = os.environ.get(key_id_var)
        raw_key_secret = os.environ.get(key_secret_var)

        if not raw_key_id or not raw_key_id.strip():
            raise ProviderCredentialResolutionError(
                f"Credential key ID environment variable '{key_id_var}' is not configured"
            )

        if not raw_key_secret or not raw_key_secret.strip():
            raise ProviderCredentialResolutionError(
                f"Credential key secret environment variable '{key_secret_var}' is not configured"
            )

        key_id = raw_key_id.strip()
        key_secret = raw_key_secret.strip()

        # 4. Enforce Razorpay test key format and fail closed on Live keys
        if key_id.startswith("rzp_live_"):
            raise ProviderLiveModeForbiddenError(
                f"Live Razorpay Key ID prefix 'rzp_live_' detected for alias '{connection.credential_ref}'. "
                "Phase 5 strictly prohibits live keys. Request failed closed."
            )

        if not key_id.startswith("rzp_test_"):
            raise ProviderInvalidKeyFormatError(
                f"Razorpay Test Mode key ID must start with 'rzp_test_'; received '{key_id[:8]}...'"
            )

        return ProviderCredentials(
            key_id=key_id,
            key_secret=SecretStr(key_secret),
        )
