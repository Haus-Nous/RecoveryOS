"""Tests for DomainEvent immutability, timestamps, and structured payloads."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.domain.events.order_events import OrderCreated
from app.domain.events.payment_events import PaymentCaptured
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.currency import Currency
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def test_event_creation_and_payload() -> None:
    evt = OrderCreated.from_order(
        order_id=OrderId("ord_123"),
        merchant_id=MerchantId("mer_abc"),
        amount=Money.from_minor(5000, Currency.INR),
        occurred_at=NOW,
    )
    assert evt.event_type == "OrderCreated"
    assert evt.aggregate_id == "ord_123"
    assert evt.aggregate_type == "Order"
    assert evt.payload["amount_minor"] == 5000
    assert evt.payload["currency"] == "INR"


def test_event_immutability() -> None:
    evt = PaymentCaptured.from_payment(
        payment_id=PaymentId("pay_123"),
        order_id=OrderId("ord_123"),
        merchant_id=MerchantId("mer_abc"),
        amount=Money.from_minor(1000, Currency.INR),
        occurred_at=NOW,
    )
    with pytest.raises(FrozenInstanceError):
        evt.aggregate_id = "modified_id"  # type: ignore
