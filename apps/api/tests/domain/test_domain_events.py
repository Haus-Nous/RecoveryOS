"""Tests for DomainEvent deep immutability, timestamps, and structured payloads."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

from app.domain.events.order_events import OrderCreated
from app.domain.events.payment_events import PaymentCaptured
from app.domain.events.recovery_events import (
    RecoveryCaseOpened,
    RecoveryVerificationFailed,
    RecoveryVerified,
)
from app.domain.types import (
    DomainEventId,
    MerchantId,
    OrderId,
    PaymentId,
    RecoveryActionId,
    RecoveryCaseId,
)
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


def test_event_attribute_immutability() -> None:
    evt = PaymentCaptured.from_payment(
        payment_id=PaymentId("pay_123"),
        order_id=OrderId("ord_123"),
        merchant_id=MerchantId("mer_abc"),
        amount=Money.from_minor(1000, Currency.INR),
        occurred_at=NOW,
    )
    with pytest.raises(FrozenInstanceError):
        evt.aggregate_id = "modified_id"  # type: ignore


def test_event_payload_deep_immutability() -> None:
    """CRITICAL: Nested collections in event payload must be strictly immutable."""
    raw_payload: dict[str, Any] = {
        "case_id": "rc_123",
        "nested_dict": {"risk_score": 85, "tags": ["high_value", "urgent"]},
        "items": [1, 2, 3],
    }
    evt = RecoveryCaseOpened(
        event_id=DomainEventId("evt_001"),
        event_type="RecoveryCaseOpened",
        aggregate_id="rc_123",
        aggregate_type="RecoveryCase",
        occurred_at=NOW,
        payload=raw_payload,
    )

    # 1. Direct key assignment on payload must raise TypeError (MappingProxyType)
    with pytest.raises(TypeError):
        evt.payload["case_id"] = "modified_rc_999"  # type: ignore

    with pytest.raises(TypeError):
        evt.payload["new_key"] = "forbidden"  # type: ignore

    # 2. Nested dictionary modification must raise TypeError
    with pytest.raises(TypeError):
        evt.payload["nested_dict"]["risk_score"] = 99

    # 3. Nested list modification must fail (converted to tuple)
    with pytest.raises(AttributeError):
        evt.payload["nested_dict"]["tags"].append("tampered")

    with pytest.raises(AttributeError):
        evt.payload["items"].append(4)


def test_recovery_verified_and_failure_events() -> None:
    verified_evt = RecoveryVerified.from_verification(
        case_id=RecoveryCaseId("rc_123"),
        action_id=RecoveryActionId("act_123"),
        verified_amount=Money.from_minor(10000, Currency.INR),
        evidence_ref="SETTLEMENT_BATCH_777",
        occurred_at=NOW,
    )
    assert verified_evt.event_type == "RecoveryVerified"
    assert verified_evt.payload["evidence_ref"] == "SETTLEMENT_BATCH_777"

    failed_evt = RecoveryVerificationFailed.from_failure(
        case_id=RecoveryCaseId("rc_123"),
        action_id=RecoveryActionId("act_123"),
        reason="Chargeback issued before settlement window closed",
        occurred_at=NOW,
    )
    assert failed_evt.event_type == "RecoveryVerificationFailed"
    assert "Chargeback" in str(failed_evt.payload["reason"])
