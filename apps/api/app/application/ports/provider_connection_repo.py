"""Repository port for PaymentProviderConnection entities."""

from typing import Protocol

from app.domain.types import MerchantId
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderMode,
)


class ProviderConnectionRepository(Protocol):
    """Tenant-scoped repository port for PaymentProviderConnection."""

    async def get_by_id(
        self, merchant_id: MerchantId, connection_id: str
    ) -> PaymentProviderConnection | None:
        """Fetch provider connection by ID scoped by merchant. Returns None if not found."""
        ...

    async def get_by_provider_and_mode(
        self, merchant_id: MerchantId, provider: PaymentProviderName, mode: ProviderMode
    ) -> list[PaymentProviderConnection]:
        """Fetch provider connections for a merchant by provider and mode."""
        ...

    async def get_by_credential_ref(
        self,
        merchant_id: MerchantId,
        provider: PaymentProviderName,
        mode: ProviderMode,
        credential_ref: str,
    ) -> PaymentProviderConnection | None:
        """Fetch specific connection by merchant, provider, mode, and credential_ref."""
        ...

    async def save(self, merchant_id: MerchantId, connection: PaymentProviderConnection) -> None:
        """Save or update a provider connection enforcing tenant ownership."""
        ...

    async def list_for_merchant(self, merchant_id: MerchantId) -> list[PaymentProviderConnection]:
        """List all provider connections for a merchant."""
        ...
