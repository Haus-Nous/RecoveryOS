"""Payment provider application service and provider registry."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from app.application.ports.payment_provider import PaymentProvider
from app.application.ports.provider_credentials import (
    ProviderCredentialResolver,
    ProviderCredentials,
)
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.types import MerchantId
from app.infrastructure.providers.razorpay.adapter import RazorpayAdapter
from app.infrastructure.providers.razorpay.client import RazorpayHttpClient
from app.providers.errors import (
    ProviderCredentialResolutionError,
    ProviderLiveModeForbiddenError,
    ProviderNotFoundError,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderConnectionVerificationResult,
    ProviderCreateOrderRequest,
    ProviderMode,
    ProviderOrderSnapshot,
    ProviderPaymentSnapshot,
)


class PaymentProviderRegistry:
    """Registry managing payment provider adapters."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def get_provider(
        self,
        connection: PaymentProviderConnection,
        credentials: ProviderCredentials,
    ) -> PaymentProvider:
        """Instantiate provider adapter for given connection and credentials."""
        if connection.provider == PaymentProviderName.RAZORPAY:
            client = RazorpayHttpClient(
                credentials=credentials,
                transport=self._transport,
            )
            return RazorpayAdapter(client=client, connection=connection)
        raise ValueError(f"Unsupported provider: {connection.provider}")


class PaymentProviderService:
    """Application service orchestrating provider interactions with tenant isolation."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        credential_resolver: ProviderCredentialResolver,
        registry: PaymentProviderRegistry | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._credential_resolver = credential_resolver
        self._registry = registry or PaymentProviderRegistry(transport=transport)
        self._transport = transport

    async def get_connection(
        self, merchant_id: MerchantId, connection_id: str
    ) -> PaymentProviderConnection:
        """Fetch connection ensuring tenant ownership."""
        async with self._uow_factory() as uow:
            connection = await uow.payment_provider_connections.get_by_id(
                merchant_id, connection_id
            )
            if connection is None:
                raise ProviderNotFoundError(
                    f"Provider connection '{connection_id}' not found for merchant '{merchant_id}'"
                )
            return connection

    async def list_connections(self, merchant_id: MerchantId) -> list[PaymentProviderConnection]:
        """List all provider connections for merchant."""
        async with self._uow_factory() as uow:
            return await uow.payment_provider_connections.list_for_merchant(merchant_id)

    async def create_connection(
        self,
        merchant_id: MerchantId,
        provider: PaymentProviderName,
        mode: ProviderMode,
        credential_ref: str,
    ) -> PaymentProviderConnection:
        """Create a new payment provider connection metadata row."""
        # 1. Enforce TEST mode
        if mode == ProviderMode.LIVE:
            raise ProviderLiveModeForbiddenError(
                "Live mode provider connection creation is strictly prohibited in Phase 5"
            )

        # 2. Enforce allowlisted alias
        if not self._credential_resolver.is_allowlisted(credential_ref):
            raise ProviderCredentialResolutionError(
                f"Credential alias '{credential_ref}' is not registered in server allowlist. "
                "Arbitrary credential aliases cannot be registered."
            )

        conn_id = f"conn_{uuid.uuid4().hex[:16]}"
        now = datetime.now(UTC)

        connection = PaymentProviderConnection(
            id=conn_id,
            merchant_id=merchant_id,
            provider=provider,
            mode=mode,
            credential_ref=credential_ref,
            status=ProviderConnectionStatus.UNVERIFIED,
            created_at=now,
            updated_at=now,
            version=1,
        )

        async with self._uow_factory() as uow:
            await uow.payment_provider_connections.save(merchant_id, connection)
            await uow.commit()

        return connection

    async def verify_connection(
        self, merchant_id: MerchantId, connection_id: str
    ) -> ProviderConnectionVerificationResult:
        """Verify credentials and connection status, updating connection to ACTIVE if valid."""
        connection = await self.get_connection(merchant_id, connection_id)

        if connection.mode == ProviderMode.LIVE:
            raise ProviderLiveModeForbiddenError(
                "Live mode execution is strictly prohibited in Phase 5"
            )

        credentials = await self._credential_resolver.resolve(connection)
        provider_adapter = self._registry.get_provider(connection, credentials)

        result = await provider_adapter.verify_connection()

        if result.is_valid:
            updated_conn = PaymentProviderConnection(
                id=connection.id,
                merchant_id=connection.merchant_id,
                provider=connection.provider,
                mode=connection.mode,
                credential_ref=connection.credential_ref,
                status=ProviderConnectionStatus.ACTIVE,
                key_id_fingerprint=result.key_id_fingerprint,
                last_verified_at=result.verified_at,
                created_at=connection.created_at,
                updated_at=datetime.now(UTC),
                version=connection.version,
            )
            async with self._uow_factory() as uow:
                await uow.payment_provider_connections.save(merchant_id, updated_conn)
                await uow.commit()

        return result

    async def create_test_order(
        self,
        merchant_id: MerchantId,
        connection_id: str,
        request: ProviderCreateOrderRequest,
    ) -> ProviderOrderSnapshot:
        """Create a test order with the configured provider connection."""
        connection = await self.get_connection(merchant_id, connection_id)

        if connection.mode == ProviderMode.LIVE:
            raise ProviderLiveModeForbiddenError(
                "Live mode execution is strictly prohibited in Phase 5"
            )

        credentials = await self._credential_resolver.resolve(connection)
        provider_adapter = self._registry.get_provider(connection, credentials)

        return await provider_adapter.create_order(request)

    async def fetch_order(
        self,
        merchant_id: MerchantId,
        connection_id: str,
        provider_order_id: str,
    ) -> ProviderOrderSnapshot:
        """Fetch order from provider."""
        connection = await self.get_connection(merchant_id, connection_id)
        credentials = await self._credential_resolver.resolve(connection)
        provider_adapter = self._registry.get_provider(connection, credentials)

        return await provider_adapter.fetch_order(provider_order_id)

    async def fetch_payment(
        self,
        merchant_id: MerchantId,
        connection_id: str,
        provider_payment_id: str,
    ) -> ProviderPaymentSnapshot:
        """Fetch payment from provider."""
        connection = await self.get_connection(merchant_id, connection_id)
        credentials = await self._credential_resolver.resolve(connection)
        provider_adapter = self._registry.get_provider(connection, credentials)

        return await provider_adapter.fetch_payment(provider_payment_id)

    async def list_order_payments(
        self,
        merchant_id: MerchantId,
        connection_id: str,
        provider_order_id: str,
    ) -> list[ProviderPaymentSnapshot]:
        """Fetch all payments associated with an order from provider."""
        connection = await self.get_connection(merchant_id, connection_id)
        credentials = await self._credential_resolver.resolve(connection)
        provider_adapter = self._registry.get_provider(connection, credentials)

        return await provider_adapter.list_payments_for_order(provider_order_id)
