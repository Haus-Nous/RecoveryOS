"""Tests for Payment aggregate, failure context, and full transition matrix."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.payment import (
    ALLOWED_PAYMENT_TRANSITIONS,
    PAYMENT_TERMINAL_STATES,
    Payment,
    PaymentState,
)
from app.domain.exceptions import (
    InvalidStateTransitionError,
    InvariantViolationError,
    TerminalStateError,
)
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.currency import Currency
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def create_payment(state: PaymentState = PaymentState.CREATED) -> Payment:
    return Payment(
        id=PaymentId("pay_123"),
        merchant_id=MerchantId("mer_abc"),
        order_id=OrderId("ord_123"),
        amount=Money.from_minor(25000, Currency.INR),
        state=state,
        attempt_number=1,
        created_at=NOW,
        updated_at=NOW,
    )


class TestPaymentStateMachine:
    def test_happy_path_lifecycle(self) -> None:
        p1 = create_payment(PaymentState.CREATED)
        p1.mark_pending(NOW)
        assert p1.state == PaymentState.PENDING

        p2 = create_payment(PaymentState.PENDING)
        p2.mark_authorized(NOW)
        assert p2.state == PaymentState.AUTHORIZED

        p3 = create_payment(PaymentState.AUTHORIZED)
        p3.capture(NOW)
        assert p3.state == PaymentState.CAPTURED
        assert not p3.is_terminal

        p4 = create_payment(PaymentState.CAPTURED)
        p4.refund(NOW, is_partial=True)
        assert p4.state == PaymentState.PARTIALLY_REFUNDED
        assert not p4.is_terminal

        p5 = create_payment(PaymentState.PARTIALLY_REFUNDED)
        p5.refund(NOW, is_partial=False)
        assert p5.state == PaymentState.REFUNDED
        assert p5.is_terminal

    def test_payment_failure_with_context(self) -> None:
        p = create_payment(PaymentState.PENDING)
        failure = PaymentFailure(
            category=FailureCategory.INSUFFICIENT_FUNDS,
            code="INSUFFICIENT_BALANCE",
            reason="Card issuer declined due to insufficient funds.",
            is_retryable_hint=True,
            occurred_at=NOW,
        )
        p.fail(failure=failure, occurred_at=NOW)
        assert p.state == PaymentState.FAILED
        assert p.failure == failure
        assert p.is_terminal

    def test_captured_to_failed_is_forbidden(self) -> None:
        p = create_payment(PaymentState.CAPTURED)
        with pytest.raises(InvalidStateTransitionError):
            p.transition_to(PaymentState.FAILED, NOW)

    def test_refunded_to_authorized_is_forbidden(self) -> None:
        p = create_payment(PaymentState.REFUNDED)
        with pytest.raises(TerminalStateError):
            p.transition_to(PaymentState.AUTHORIZED, NOW)

    def test_cancelled_to_captured_is_forbidden(self) -> None:
        p = create_payment(PaymentState.CANCELLED)
        with pytest.raises(TerminalStateError):
            p.transition_to(PaymentState.CAPTURED, NOW)

    def test_attempt_number_invariant(self) -> None:
        with pytest.raises(InvariantViolationError):
            Payment(
                id=PaymentId("pay_123"),
                merchant_id=MerchantId("mer_abc"),
                order_id=OrderId("ord_123"),
                amount=Money.from_minor(1000, Currency.INR),
                state=PaymentState.CREATED,
                attempt_number=0,
                created_at=NOW,
                updated_at=NOW,
            )

    @pytest.mark.parametrize("from_state", list(PaymentState))
    @pytest.mark.parametrize("to_state", list(PaymentState))
    def test_complete_payment_transition_matrix(
        self, from_state: PaymentState, to_state: PaymentState
    ) -> None:
        """Exhaustively verify all Payment state transition pairs."""
        p = create_payment(from_state)
        is_allowed = to_state in ALLOWED_PAYMENT_TRANSITIONS[from_state]

        if from_state == to_state:
            p.transition_to(to_state, NOW)
            assert p.state == from_state
        elif is_allowed:
            p.transition_to(to_state, NOW)
            assert p.state == to_state
        else:
            if from_state in PAYMENT_TERMINAL_STATES:
                with pytest.raises(TerminalStateError):
                    p.transition_to(to_state, NOW)
            else:
                with pytest.raises(InvalidStateTransitionError):
                    p.transition_to(to_state, NOW)
