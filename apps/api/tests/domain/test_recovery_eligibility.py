"""Tests for pure domain recovery eligibility evaluation service."""

from datetime import UTC, datetime

from app.domain.entities.payment import Payment, PaymentState
from app.domain.services.recovery_eligibility import check_recovery_eligibility
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.currency import Currency
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def test_eligible_failed_payment() -> None:
    payment = Payment(
        id=PaymentId("pay_123"),
        merchant_id=MerchantId("mer_abc"),
        order_id=OrderId("ord_123"),
        amount=Money.from_minor(20000, Currency.INR),
        state=PaymentState.FAILED,
        attempt_number=1,
        created_at=NOW,
        updated_at=NOW,
        failure=PaymentFailure(
            category=FailureCategory.INSUFFICIENT_FUNDS,
            code="INSUFFICIENT_FUNDS",
            reason="Card declined",
            is_retryable_hint=True,
            occurred_at=NOW,
        ),
    )
    is_eligible, reason = check_recovery_eligibility(payment)
    assert is_eligible
    assert reason is None


def test_ineligible_captured_payment() -> None:
    payment = Payment(
        id=PaymentId("pay_123"),
        merchant_id=MerchantId("mer_abc"),
        order_id=OrderId("ord_123"),
        amount=Money.from_minor(20000, Currency.INR),
        state=PaymentState.CAPTURED,
        attempt_number=1,
        created_at=NOW,
        updated_at=NOW,
    )
    is_eligible, reason = check_recovery_eligibility(payment)
    assert not is_eligible
    assert "only FAILED payments can open recovery case" in str(reason)
