"""Provider credentials port and redacted value objects."""

from typing import Protocol

from pydantic import BaseModel, ConfigDict, SecretStr

from app.providers.types import PaymentProviderConnection


class ProviderCredentials(BaseModel):
    """Ephemeral in-memory provider credentials with strict redaction guarantees."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    key_id: str
    key_secret: SecretStr

    def __repr__(self) -> str:
        return f"<ProviderCredentials key_id='{self.key_id}' key_secret='[REDACTED]'>"

    def __str__(self) -> str:
        return f"ProviderCredentials(key_id='{self.key_id}', key_secret='[REDACTED]')"


class ProviderCredentialResolver(Protocol):
    """Protocol for resolving ephemeral credentials for a provider connection."""

    def is_allowlisted(self, credential_ref: str) -> bool:
        """Check whether credential_ref exists in server allowlist."""
        ...

    async def resolve(self, connection: PaymentProviderConnection) -> ProviderCredentials:
        """Resolve ephemeral credentials for connection or raise ProviderCredentialResolutionError."""
        ...
