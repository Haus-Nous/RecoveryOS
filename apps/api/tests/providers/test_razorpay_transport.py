from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from app.application.ports.provider_credentials import ProviderCredentials
from app.infrastructure.providers.razorpay.adapter import RazorpayAdapter
from app.infrastructure.providers.razorpay.client import (
    MAX_PROVIDER_RESPONSE_BYTES,
    RazorpayHttpClient,
)
from app.providers.errors import (
    ProviderAmbiguityError,
    ProviderAmbiguousWriteError,
    ProviderAuthenticationError,
    ProviderLiveModeForbiddenError,
    ProviderResponseTooLargeError,
    ProviderValidationError,
)
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderCreateOrderRequest,
    ProviderMode,
    ProviderOrderStatus,
)


@pytest.fixture
def test_connection() -> PaymentProviderConnection:
    return PaymentProviderConnection(
        id="conn_transport_001",
        merchant_id="m_transport_merchant",
        provider=PaymentProviderName.RAZORPAY,
        mode=ProviderMode.TEST,
        credential_ref="RAZORPAY_TEST_DEMO",
        status=ProviderConnectionStatus.ACTIVE,
    )


@pytest.fixture
def credentials() -> ProviderCredentials:
    return ProviderCredentials(
        key_id="rzp_test_transportKey1",
        key_secret=SecretStr("secretKeyVal12345"),
    )


@pytest.mark.asyncio
async def test_client_defaults_security_and_tls(credentials: ProviderCredentials) -> None:
    client = RazorpayHttpClient(credentials=credentials)
    try:
        assert client._client.follow_redirects is False
        assert client.verify is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_live_key_hard_block_in_client() -> None:
    live_creds = ProviderCredentials(
        key_id="rzp_live_forbiddenKey",
        key_secret=SecretStr("secret123"),
    )
    with pytest.raises(ProviderLiveModeForbiddenError, match="Live Razorpay Key ID prefix"):
        RazorpayHttpClient(credentials=live_creds)


@pytest.mark.asyncio
async def test_streamed_oversized_response_with_content_length_fails_early(
    credentials: ProviderCredentials,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # Header specifies 2MB
        headers = {"Content-Length": str(MAX_PROVIDER_RESPONSE_BYTES + 500)}
        return httpx.Response(200, headers=headers, content=b"{}")

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderResponseTooLargeError, match="exceeds limit"):
            await client.get("/v1/orders")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_streamed_oversized_response_without_content_length_fails_on_stream(
    credentials: ProviderCredentials,
) -> None:
    class ChunkStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            for _ in range(20):
                yield b"x" * 65536

    def handler(request: httpx.Request) -> httpx.Response:
        # No Content-Length header, streamed response
        return httpx.Response(200, stream=ChunkStream())

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderResponseTooLargeError, match="exceeded maximum allowed limit"):
            await client.get("/v1/orders")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_safe_get_retry_on_503(credentials: ProviderCredentials) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(
                503, json={"error": {"code": "SERVER_ERROR", "description": "Gateway busy"}}
            )
        return httpx.Response(200, json={"id": "order_recovered", "entity": "order"})

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(
        credentials=credentials, transport=transport, max_retries=3, backoff_base_seconds=0.01
    )
    try:
        data = await client.get("/v1/orders/order_recovered")
        assert data["id"] == "order_recovered"
        assert attempts == 3
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_safe_get_retry_rate_limit_429_capped(credentials: ProviderCredentials) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # Send excessive Retry-After: 9999 seconds; client must cap at MAX_RETRY_AFTER_SECONDS (5.0s)
            return httpx.Response(
                429, headers={"Retry-After": "9999"}, json={"error": {"code": "TOO_MANY_REQUESTS"}}
            )
        return httpx.Response(200, json={"id": "order_rate_recovered"})

    transport = httpx.MockTransport(handler)
    # Use max_retries=2, monkeypatch sleep to not delay test
    client = RazorpayHttpClient(
        credentials=credentials, transport=transport, max_retries=2, backoff_base_seconds=0.01
    )
    try:
        data = await client.get("/v1/orders/order_rate_recovered")
        assert data["id"] == "order_rate_recovered"
        assert attempts == 2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_post_orders_never_blindly_retries(credentials: ProviderCredentials) -> None:
    post_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count
        if request.method == "POST":
            post_count += 1
            raise httpx.ReadTimeout("Socket timed out during order creation")
        return httpx.Response(200, json={"items": []})

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderAmbiguousWriteError, match="write state is ambiguous"):
            await client.post(
                "/v1/orders",
                {"amount": 1000, "currency": "INR", "receipt": "rcpt_unique_01"},
                receipt="rcpt_unique_01",
            )

        # CRITICAL ASSERTION: Exactly 1 POST attempt was made; never retried
        assert post_count == 1
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_ambiguous_write_receipt_recovery_single_match(
    test_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    post_count = 0
    get_receipt_count = 0
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count, get_receipt_count, captured_params
        if request.method == "POST":
            post_count += 1
            # Simulate upstream read timeout after order may or may not have committed
            raise httpx.ReadTimeout("Simulated write timeout")
        elif request.method == "GET" and request.url.path == "/v1/orders":
            get_receipt_count += 1
            captured_params = dict(request.url.params)
            # Upstream did create the order! Return exactly 1 match
            return httpx.Response(
                200,
                json={
                    "entity": "collection",
                    "count": 1,
                    "items": [
                        {
                            "id": "order_recovered_via_receipt",
                            "entity": "order",
                            "amount": 50000,
                            "currency": "INR",
                            "status": "created",
                            "receipt": "rcpt_ambiguous_100",
                            "created_at": 1700000000,
                        }
                    ],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=test_connection)

    # Perform create_order
    snapshot = await adapter.create_order(
        ProviderCreateOrderRequest(
            amount_minor=50000,
            currency="INR",
            receipt="rcpt_ambiguous_100",
        )
    )

    # Invariants verification:
    assert post_count == 1, "POST must never be retried blindly"
    assert get_receipt_count == 1, "Must query GET /v1/orders to inspect receipt"
    # Mandatory Amendment 1 & 8: Verify receipt query parameter is sent directly to Razorpay API
    assert captured_params.get("receipt") == "rcpt_ambiguous_100", (
        "Query parameter 'receipt' must be sent directly"
    )
    assert snapshot.provider_order_id == "order_recovered_via_receipt"
    assert snapshot.status == ProviderOrderStatus.CREATED


@pytest.mark.asyncio
async def test_ambiguous_write_receipt_recovery_zero_match_reraises(
    test_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise httpx.ReadTimeout("Simulated write timeout")
        elif request.method == "GET" and request.url.path == "/v1/orders":
            # Zero matches found
            return httpx.Response(200, json={"entity": "collection", "count": 0, "items": []})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=test_connection)

    with pytest.raises(ProviderAmbiguousWriteError):
        await adapter.create_order(
            ProviderCreateOrderRequest(
                amount_minor=50000,
                currency="INR",
                receipt="rcpt_zero_match",
            )
        )


@pytest.mark.asyncio
async def test_ambiguous_write_receipt_recovery_multiple_match_raises_ambiguity_error(
    test_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise httpx.ReadTimeout("Simulated write timeout")
        elif request.method == "GET" and request.url.path == "/v1/orders":
            # Upstream integrity violation: multiple orders with same receipt
            return httpx.Response(
                200,
                json={
                    "entity": "collection",
                    "count": 2,
                    "items": [
                        {
                            "id": "order_1",
                            "entity": "order",
                            "amount": 50000,
                            "currency": "INR",
                            "status": "created",
                            "receipt": "rcpt_duplicate",
                            "created_at": 1700000000,
                        },
                        {
                            "id": "order_2",
                            "entity": "order",
                            "amount": 50000,
                            "currency": "INR",
                            "status": "created",
                            "receipt": "rcpt_duplicate",
                            "created_at": 1700000000,
                        },
                    ],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=test_connection)

    with pytest.raises(ProviderAmbiguityError, match="Multiple orders"):
        await adapter.create_order(
            ProviderCreateOrderRequest(
                amount_minor=50000,
                currency="INR",
                receipt="rcpt_duplicate",
            )
        )


@pytest.mark.asyncio
async def test_razorpay_400_authentication_failed_mapping(credentials: ProviderCredentials) -> None:
    # Mandatory Amendment 2: Razorpay returns 400 for Authentication failed, must map to ProviderAuthenticationError
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "BAD_REQUEST_ERROR",
                    "description": "Authentication failed",
                    "source": "NA",
                    "step": "NA",
                    "reason": "NA",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderAuthenticationError, match="Authentication failed"):
            await client.get("/v1/orders")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_razorpay_401_authentication_error_mapping(credentials: ProviderCredentials) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "error": {
                    "code": "BAD_REQUEST_ERROR",
                    "description": "The id provided does not exist or invalid credentials",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderAuthenticationError, match="Provider authentication failed"):
            await client.get("/v1/orders")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_razorpay_400_validation_error_mapping(credentials: ProviderCredentials) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "BAD_REQUEST_ERROR",
                    "description": "amount must be at least 100 paise",
                    "field": "amount",
                }
            },
        )

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    try:
        with pytest.raises(ProviderValidationError, match="amount must be at least 100 paise"):
            await client.get("/v1/orders")
    finally:
        await client.close()
