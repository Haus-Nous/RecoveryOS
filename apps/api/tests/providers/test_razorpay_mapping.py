"""Tests for Razorpay response mapping, unknown enum handling, and PII redaction."""

from datetime import datetime

import pytest

from app.infrastructure.providers.razorpay.mapper import RazorpayMapper
from app.providers.errors import (
    ProviderMalformedResponseError,
    ProviderUnsupportedCurrencyError,
)
from app.providers.types import (
    PaymentProviderName,
    ProviderOrderStatus,
    ProviderPaymentMethod,
    ProviderPaymentStatus,
)


def test_order_mapping_valid() -> None:
    data = {
        "id": "order_12345",
        "amount": 25000,
        "currency": "INR",
        "status": "created",
        "receipt": "rcpt_99",
        "created_at": 1700000000,
        "notes": {"source": "checkout"},
    }
    snapshot = RazorpayMapper.map_order(data, connection_id="conn_abc")
    assert snapshot.provider == PaymentProviderName.RAZORPAY
    assert snapshot.provider_order_id == "order_12345"
    assert snapshot.merchant_connection_id == "conn_abc"
    assert snapshot.amount_minor == 25000
    assert snapshot.currency == "INR"
    assert snapshot.status == ProviderOrderStatus.CREATED
    assert snapshot.receipt == "rcpt_99"
    assert snapshot.raw_status == "created"
    assert snapshot.notes == {"source": "checkout"}
    assert isinstance(snapshot.created_at, datetime)


def test_order_mapping_unknown_status_failsafe() -> None:
    data = {
        "id": "order_12345",
        "amount": 1000,
        "currency": "INR",
        "status": "future_unknown_state",
        "created_at": 1700000000,
    }
    snapshot = RazorpayMapper.map_order(data, connection_id="conn_abc")
    assert snapshot.status == ProviderOrderStatus.UNKNOWN
    assert snapshot.raw_status == "future_unknown_state"


def test_order_mapping_missing_required_fields_raises_malformed() -> None:
    # Missing ID
    with pytest.raises(ProviderMalformedResponseError, match="missing required 'id'"):
        RazorpayMapper.map_order(
            {"amount": 1000, "currency": "INR", "created_at": 1700000000}, connection_id="conn_abc"
        )

    # Missing amount
    with pytest.raises(ProviderMalformedResponseError, match="missing required integer 'amount'"):
        RazorpayMapper.map_order(
            {"id": "order_123", "currency": "INR", "created_at": 1700000000},
            connection_id="conn_abc",
        )


def test_order_mapping_invalid_currency_raises_unsupported_currency() -> None:
    data = {
        "id": "order_12345",
        "amount": 1000,
        "currency": "TOOLONG",
        "status": "created",
        "created_at": 1700000000,
    }
    with pytest.raises(ProviderUnsupportedCurrencyError, match="Unsupported provider currency"):
        RazorpayMapper.map_order(data, connection_id="conn_abc")


def test_payment_mapping_captured_method_card() -> None:
    data = {
        "id": "pay_98765",
        "order_id": "order_12345",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "method": "card",
        "created_at": 1700000050,
        "fee": 118,
        "tax": 18,
    }
    snapshot = RazorpayMapper.map_payment(data)
    assert snapshot.provider == PaymentProviderName.RAZORPAY
    assert snapshot.provider_payment_id == "pay_98765"
    assert snapshot.order_id == "order_12345"
    assert snapshot.amount_minor == 50000
    assert snapshot.status == ProviderPaymentStatus.CAPTURED
    assert snapshot.method == ProviderPaymentMethod.CARD
    assert snapshot.fee_minor == 118
    assert snapshot.tax_minor == 18
    assert snapshot.failure is None


def test_payment_mapping_unknown_status_and_method_failsafe() -> None:
    data = {
        "id": "pay_98765",
        "amount": 1000,
        "currency": "INR",
        "status": "some_novel_status",
        "method": "crypto_future",
        "created_at": 1700000050,
    }
    snapshot = RazorpayMapper.map_payment(data)
    assert snapshot.status == ProviderPaymentStatus.UNKNOWN
    assert snapshot.raw_status == "some_novel_status"
    assert snapshot.method == ProviderPaymentMethod.OTHER


def test_payment_mapping_pii_strictly_stripped() -> None:
    data = {
        "id": "pay_98765",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "method": "card",
        "created_at": 1700000050,
        # Sensitive PII fields that must be scrubbed:
        "email": "victim_or_customer@example.com",
        "contact": "+919999999999",
        "card_id": "card_secret_123",
        "card": {"number": "411111******1111", "network": "Visa"},
        "vpa": "user@paytm",
        "bank": "HDFC",
    }
    snapshot = RazorpayMapper.map_payment(data)

    # 1. Check raw_data dict in snapshot does NOT contain any PII
    for pii_field in ["email", "contact", "card_id", "card", "vpa", "bank"]:
        assert pii_field not in snapshot.raw_data, f"PII field '{pii_field}' leaked in raw_data!"

    # 2. Check snapshot serialization
    dumped = snapshot.model_dump(mode="json")
    for pii_field in ["email", "contact", "card_id", "card", "vpa", "bank"]:
        assert pii_field not in dumped.get("raw_data", {}), (
            f"PII field '{pii_field}' leaked in serialized raw_data!"
        )


def test_payment_mapping_failure_details_captured() -> None:
    data = {
        "id": "pay_failed_1",
        "amount": 50000,
        "currency": "INR",
        "status": "failed",
        "method": "upi",
        "created_at": 1700000050,
        "error_code": "BAD_REQUEST_ERROR",
        "error_description": "Payment was declined by issuing bank",
        "error_source": "bank",
        "error_step": "payment_authorization",
        "error_reason": "payment_failed",
    }
    snapshot = RazorpayMapper.map_payment(data)
    assert snapshot.status == ProviderPaymentStatus.FAILED
    assert snapshot.failure is not None
    assert snapshot.failure.code == "BAD_REQUEST_ERROR"
    assert snapshot.failure.description == "Payment was declined by issuing bank"
    assert snapshot.failure.source == "bank"
    assert snapshot.failure.step == "payment_authorization"
    assert snapshot.failure.reason == "payment_failed"


def test_payment_mapping_missing_id_or_amount_raises_malformed() -> None:
    with pytest.raises(ProviderMalformedResponseError, match="missing required 'id'"):
        RazorpayMapper.map_payment({"amount": 1000, "currency": "INR", "created_at": 1700000000})

    with pytest.raises(ProviderMalformedResponseError, match="missing required integer 'amount'"):
        RazorpayMapper.map_payment({"id": "pay_123", "currency": "INR", "created_at": 1700000000})
