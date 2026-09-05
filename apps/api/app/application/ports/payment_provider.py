"""Provider-independent payment provider interface (port)."""

from typing import Protocol

from app.providers.types import (
    ProviderConnectionVerificationResult,
    ProviderCreateOrderRequest,
    ProviderOrderSnapshot,
    ProviderPaymentSnapshot,
)


class PaymentProvider(Protocol):
    """Protocol defining provider-independent payment provider capabilities.

    Explicit Non-Goals in Phase 5:
    - NO capture_payment
    - NO refund_payment
    - NO retry_payment
    - NO send_payment_link
    - NO create_recovery_action
    """

    async def create_order(self, request: ProviderCreateOrderRequest) -> ProviderOrderSnapshot:
        """Create an order with the provider."""
        ...

    async def fetch_order(self, provider_order_id: str) -> ProviderOrderSnapshot:
        """Fetch an order by its provider ID."""
        ...

    async def fetch_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        """Fetch a payment by its provider ID."""
        ...

    async def list_payments_for_order(
        self, provider_order_id: str, count: int = 10, skip: int = 0
    ) -> list[ProviderPaymentSnapshot]:
        """Fetch all payments associated with an order ID."""
        ...

    async def verify_connection(self) -> ProviderConnectionVerificationResult:
        """Verify credentials and connection status using a safe read-only operation."""
        ...

    async def find_orders_by_receipt(self, receipt: str) -> list[ProviderOrderSnapshot]:
        """Find orders by exact receipt for ambiguous write recovery."""
        ...
