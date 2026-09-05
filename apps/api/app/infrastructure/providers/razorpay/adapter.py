"""Razorpay adapter implementing the PaymentProvider port for Test Mode operations."""

from datetime import UTC, datetime
from typing import Any

from app.application.ports.payment_provider import PaymentProvider
from app.infrastructure.providers.razorpay.client import RazorpayHttpClient
from app.infrastructure.providers.razorpay.mapper import RazorpayMapper
from app.providers.errors import (
    ProviderAmbiguityError,
    ProviderAmbiguousWriteError,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionVerificationResult,
    ProviderCreateOrderRequest,
    ProviderOrderSnapshot,
    ProviderPaymentSnapshot,
)


class RazorpayAdapter(PaymentProvider):
    """Adapter translating provider-neutral operations into Razorpay Test Mode REST calls."""

    def __init__(
        self,
        client: RazorpayHttpClient,
        connection: PaymentProviderConnection,
    ) -> None:
        self._client = client
        self._connection = connection

    async def create_order(self, request: ProviderCreateOrderRequest) -> ProviderOrderSnapshot:
        """Create an order at Razorpay with safe ambiguous-write receipt recovery.

        INVARIANT:
        If POST /v1/orders fails with an ambiguous network error, do NOT blindly POST again.
        Instead, query GET /v1/orders?receipt=<receipt>.
        """
        payload: dict[str, Any] = {
            "amount": request.amount_minor,
            "currency": request.currency,
            "receipt": request.receipt,
        }
        if request.notes:
            payload["notes"] = request.notes
        if request.partial_payment:
            payload["partial_payment"] = True

        try:
            data = await self._client.post("/v1/orders", payload, receipt=request.receipt)
            return RazorpayMapper.map_order(data, connection_id=self._connection.id)
        except ProviderAmbiguousWriteError as exc:
            # Ambiguous write recovery: query orders by exact receipt
            matching_orders = await self.find_orders_by_receipt(request.receipt)
            if len(matching_orders) == 1:
                return matching_orders[0]
            if len(matching_orders) == 0:
                # Still ambiguous: write may have failed or might still commit upstream
                raise
            raise ProviderAmbiguityError(
                f"Multiple orders ({len(matching_orders)}) matched receipt '{request.receipt}'; upstream integrity error"
            ) from exc

    async def fetch_order(self, provider_order_id: str) -> ProviderOrderSnapshot:
        """Fetch an order by its Razorpay ID."""
        data = await self._client.get(f"/v1/orders/{provider_order_id}")
        return RazorpayMapper.map_order(data, connection_id=self._connection.id)

    async def fetch_payment(self, provider_payment_id: str) -> ProviderPaymentSnapshot:
        """Fetch a payment by its Razorpay ID with PII stripped."""
        data = await self._client.get(f"/v1/payments/{provider_payment_id}")
        return RazorpayMapper.map_payment(data)

    async def list_payments_for_order(
        self, provider_order_id: str, count: int = 10, skip: int = 0
    ) -> list[ProviderPaymentSnapshot]:
        """Fetch all payments associated with an order ID."""
        params = {"count": min(count, 100), "skip": max(skip, 0)}
        data = await self._client.get(f"/v1/orders/{provider_order_id}/payments", params=params)
        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        return [RazorpayMapper.map_payment(p) for p in items if isinstance(p, dict)]

    async def find_orders_by_receipt(self, receipt: str) -> list[ProviderOrderSnapshot]:
        """Query orders directly using receipt filter parameter."""
        params = {"receipt": receipt}
        data = await self._client.get("/v1/orders", params=params)
        items = data.get("items", [])
        if not isinstance(items, list):
            return []
        return [
            RazorpayMapper.map_order(o, connection_id=self._connection.id)
            for o in items
            if isinstance(o, dict) and o.get("receipt") == receipt
        ]

    async def verify_connection(self) -> ProviderConnectionVerificationResult:
        """Verify credentials and connection status using a safe read-only operation."""
        # Safe read request with count=1; creates no money-moving state
        await self._client.get("/v1/orders", params={"count": 1})
        key_id = self._client._credentials.key_id
        fingerprint = f"{key_id[:9]}...{key_id[-4:]}" if len(key_id) > 13 else key_id

        return ProviderConnectionVerificationResult(
            is_valid=True,
            verified_at=datetime.now(UTC),
            provider=PaymentProviderName.RAZORPAY,
            mode=self._connection.mode,
            key_id_fingerprint=fingerprint,
            message="Razorpay connection verified successfully in Test Mode",
        )
