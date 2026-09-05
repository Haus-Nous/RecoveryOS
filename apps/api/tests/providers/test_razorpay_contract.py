"""Contract tests for Razorpay REST API responses.

Verifies that official Razorpay API fixture payloads normalize cleanly into
RecoveryOS provider snapshot types.
"""

import json
from datetime import datetime

import httpx
import pytest
from pydantic import SecretStr

from app.application.ports.provider_credentials import ProviderCredentials
from app.infrastructure.providers.razorpay.adapter import RazorpayAdapter
from app.infrastructure.providers.razorpay.client import RazorpayHttpClient
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderCreateOrderRequest,
    ProviderMode,
    ProviderOrderStatus,
    ProviderPaymentMethod,
    ProviderPaymentStatus,
)

# Official Razorpay Fixture: POST /v1/orders response
FIXTURE_ORDER_CREATED = {
    "id": "order_EKwxwAgItmmXdp",
    "entity": "order",
    "amount": 50000,
    "amount_paid": 0,
    "amount_due": 50000,
    "currency": "INR",
    "receipt": "rcpt_recov_001",
    "offer_id": None,
    "status": "created",
    "attempts": 0,
    "notes": {"internal_plan": "pro_monthly", "recovery_id": "rec_789"},
    "created_at": 1567674606,
}

# Official Razorpay Fixture: GET /v1/orders/{id} (paid)
FIXTURE_ORDER_PAID = {
    "id": "order_EKwxwAgItmmXdp",
    "entity": "order",
    "amount": 50000,
    "amount_paid": 50000,
    "amount_due": 0,
    "currency": "INR",
    "receipt": "rcpt_recov_001",
    "offer_id": None,
    "status": "paid",
    "attempts": 1,
    "notes": {"internal_plan": "pro_monthly"},
    "created_at": 1567674606,
}

# Official Razorpay Fixture: GET /v1/payments/{id} (captured card payment with customer details)
FIXTURE_PAYMENT_CAPTURED = {
    "id": "pay_29PSczAwuz6mHd",
    "entity": "payment",
    "amount": 50000,
    "currency": "INR",
    "status": "captured",
    "order_id": "order_EKwxwAgItmmXdp",
    "invoice_id": None,
    "international": False,
    "method": "card",
    "amount_refunded": 0,
    "refund_status": None,
    "captured": True,
    "description": "Subscription Payment",
    "card_id": "card_29PSczAwuz6mHd",
    "bank": None,
    "wallet": None,
    "vpa": None,
    "email": "customer@example.com",
    "contact": "+919876543210",
    "notes": {"merchant_order": "ORD-1234"},
    "fee": 1180,
    "tax": 180,
    "error_code": None,
    "error_description": None,
    "error_source": None,
    "error_step": None,
    "error_reason": None,
    "created_at": 1567674650,
}

# Official Razorpay Fixture: GET /v1/payments/{id} (failed UPI payment)
FIXTURE_PAYMENT_FAILED = {
    "id": "pay_Failed12345678",
    "entity": "payment",
    "amount": 50000,
    "currency": "INR",
    "status": "failed",
    "order_id": "order_EKwxwAgItmmXdp",
    "invoice_id": None,
    "international": False,
    "method": "upi",
    "amount_refunded": 0,
    "refund_status": None,
    "captured": False,
    "description": "Subscription Payment",
    "card_id": None,
    "bank": None,
    "wallet": None,
    "vpa": "customer@okhdfcbank",
    "email": "customer@example.com",
    "contact": "+919876543210",
    "notes": {},
    "fee": None,
    "tax": None,
    "error_code": "BAD_REQUEST_ERROR",
    "error_description": "Payment was declined by the bank due to insufficient funds.",
    "error_source": "bank",
    "error_step": "payment_authorization",
    "error_reason": "payment_failed",
    "created_at": 1567674680,
}

# Official Razorpay Fixture: GET /v1/orders/{id}/payments
FIXTURE_ORDER_PAYMENTS = {
    "entity": "collection",
    "count": 2,
    "items": [FIXTURE_PAYMENT_FAILED, FIXTURE_PAYMENT_CAPTURED],
}


@pytest.fixture
def dummy_connection() -> PaymentProviderConnection:
    return PaymentProviderConnection(
        id="conn_test_001",
        merchant_id="m_test_merchant",
        provider=PaymentProviderName.RAZORPAY,
        mode=ProviderMode.TEST,
        credential_ref="RAZORPAY_TEST_DEMO",
        status=ProviderConnectionStatus.ACTIVE,
    )


@pytest.fixture
def credentials() -> ProviderCredentials:
    return ProviderCredentials(
        key_id="rzp_test_fixtureKeyId",
        key_secret=SecretStr("fixtureSecretKey123"),
    )


@pytest.mark.asyncio
async def test_create_order_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/orders"
        body = json.loads(request.read())
        assert body["amount"] == 50000
        assert body["currency"] == "INR"
        assert body["receipt"] == "rcpt_recov_001"
        return httpx.Response(200, json=FIXTURE_ORDER_CREATED)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    snapshot = await adapter.create_order(
        ProviderCreateOrderRequest(
            amount_minor=50000,
            currency="INR",
            receipt="rcpt_recov_001",
            notes={"internal_plan": "pro_monthly", "recovery_id": "rec_789"},
        )
    )

    assert snapshot.provider == PaymentProviderName.RAZORPAY
    assert snapshot.provider_order_id == "order_EKwxwAgItmmXdp"
    assert snapshot.merchant_connection_id == "conn_test_001"
    assert snapshot.amount_minor == 50000
    assert snapshot.currency == "INR"
    assert snapshot.status == ProviderOrderStatus.CREATED
    assert snapshot.receipt == "rcpt_recov_001"
    assert snapshot.raw_status == "created"
    assert snapshot.notes["recovery_id"] == "rec_789"
    assert isinstance(snapshot.created_at, datetime)


@pytest.mark.asyncio
async def test_fetch_order_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/orders/order_EKwxwAgItmmXdp"
        return httpx.Response(200, json=FIXTURE_ORDER_PAID)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    snapshot = await adapter.fetch_order("order_EKwxwAgItmmXdp")

    assert snapshot.provider_order_id == "order_EKwxwAgItmmXdp"
    assert snapshot.status == ProviderOrderStatus.PAID
    assert snapshot.raw_status == "paid"
    assert snapshot.amount_minor == 50000


@pytest.mark.asyncio
async def test_fetch_payment_captured_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/payments/pay_29PSczAwuz6mHd"
        return httpx.Response(200, json=FIXTURE_PAYMENT_CAPTURED)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    snapshot = await adapter.fetch_payment("pay_29PSczAwuz6mHd")

    assert snapshot.provider == PaymentProviderName.RAZORPAY
    assert snapshot.provider_payment_id == "pay_29PSczAwuz6mHd"
    assert snapshot.order_id == "order_EKwxwAgItmmXdp"
    assert snapshot.amount_minor == 50000
    assert snapshot.currency == "INR"
    assert snapshot.status == ProviderPaymentStatus.CAPTURED
    assert snapshot.method == ProviderPaymentMethod.CARD
    assert snapshot.fee_minor == 1180
    assert snapshot.tax_minor == 180
    assert snapshot.failure is None

    # CRITICAL PII STRIPPING VERIFICATION
    assert "email" not in snapshot.raw_data
    assert "contact" not in snapshot.raw_data
    assert "card" not in snapshot.raw_data
    assert "card_id" not in snapshot.raw_data
    assert "vpa" not in snapshot.raw_data
    assert "bank" not in snapshot.raw_data


@pytest.mark.asyncio
async def test_fetch_payment_failed_with_details_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/payments/pay_Failed12345678"
        return httpx.Response(200, json=FIXTURE_PAYMENT_FAILED)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    snapshot = await adapter.fetch_payment("pay_Failed12345678")

    assert snapshot.status == ProviderPaymentStatus.FAILED
    assert snapshot.method == ProviderPaymentMethod.UPI
    assert snapshot.failure is not None
    assert snapshot.failure.code == "BAD_REQUEST_ERROR"
    assert snapshot.failure.reason == "payment_failed"
    assert snapshot.failure.source == "bank"
    assert snapshot.failure.step == "payment_authorization"
    assert snapshot.failure.description is not None
    assert "insufficient funds" in snapshot.failure.description.lower()

    # PII stripped even in failure
    assert "vpa" not in snapshot.raw_data
    assert "email" not in snapshot.raw_data
    assert "contact" not in snapshot.raw_data


@pytest.mark.asyncio
async def test_list_order_payments_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/orders/order_EKwxwAgItmmXdp/payments"
        assert request.url.params["count"] == "10"
        return httpx.Response(200, json=FIXTURE_ORDER_PAYMENTS)

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    payments = await adapter.list_payments_for_order("order_EKwxwAgItmmXdp")

    assert len(payments) == 2
    assert payments[0].provider_payment_id == "pay_Failed12345678"
    assert payments[0].status == ProviderPaymentStatus.FAILED
    assert payments[1].provider_payment_id == "pay_29PSczAwuz6mHd"
    assert payments[1].status == ProviderPaymentStatus.CAPTURED


@pytest.mark.asyncio
async def test_verify_connection_contract(
    dummy_connection: PaymentProviderConnection, credentials: ProviderCredentials
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/orders"
        assert request.url.params["count"] == "1"
        return httpx.Response(200, json={"entity": "collection", "count": 0, "items": []})

    transport = httpx.MockTransport(handler)
    client = RazorpayHttpClient(credentials=credentials, transport=transport)
    adapter = RazorpayAdapter(client=client, connection=dummy_connection)

    result = await adapter.verify_connection()

    assert result.is_valid is True
    assert result.provider == PaymentProviderName.RAZORPAY
    assert result.mode == ProviderMode.TEST
    assert result.key_id_fingerprint is not None
    assert "rzp_test_" in result.key_id_fingerprint
