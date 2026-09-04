"""Payment attempt aggregate and state machine."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.exceptions import (
    InvalidStateTransitionError,
    InvariantViolationError,
    TerminalStateError,
)
from app.domain.types import MerchantId, OrderId, PaymentId, ensure_utc_datetime
from app.domain.values.failure import PaymentFailure
from app.domain.values.money import Money


class PaymentState(StrEnum):
    """Canonical payment lifecycle states."""

    CREATED = "CREATED"
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


ALLOWED_PAYMENT_TRANSITIONS: dict[PaymentState, frozenset[PaymentState]] = {
    PaymentState.CREATED: frozenset(
        {
            PaymentState.PENDING,
            PaymentState.AUTHORIZED,
            PaymentState.CAPTURED,
            PaymentState.FAILED,
            PaymentState.CANCELLED,
        }
    ),
    PaymentState.PENDING: frozenset(
        {
            PaymentState.AUTHORIZED,
            PaymentState.CAPTURED,
            PaymentState.FAILED,
            PaymentState.CANCELLED,
        }
    ),
    PaymentState.AUTHORIZED: frozenset(
        {
            PaymentState.CAPTURED,
            PaymentState.FAILED,
            PaymentState.CANCELLED,
        }
    ),
    PaymentState.CAPTURED: frozenset(
        {
            PaymentState.PARTIALLY_REFUNDED,
            PaymentState.REFUNDED,
        }
    ),
    PaymentState.PARTIALLY_REFUNDED: frozenset(
        {
            PaymentState.PARTIALLY_REFUNDED,
            PaymentState.REFUNDED,
        }
    ),
    PaymentState.FAILED: frozenset(),  # Terminal
    PaymentState.CANCELLED: frozenset(),  # Terminal
    PaymentState.REFUNDED: frozenset(),  # Terminal
}

PAYMENT_TERMINAL_STATES: frozenset[PaymentState] = frozenset(
    {
        PaymentState.FAILED,
        PaymentState.CANCELLED,
        PaymentState.REFUNDED,
    }
)


@dataclass(slots=True)
class Payment:
    """Canonical payment attempt aggregate independent of PSP."""

    id: PaymentId
    merchant_id: MerchantId
    order_id: OrderId
    amount: Money
    state: PaymentState
    attempt_number: int
    created_at: datetime
    updated_at: datetime
    failure: PaymentFailure | None = None
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        self.created_at = ensure_utc_datetime(self.created_at)
        self.updated_at = ensure_utc_datetime(self.updated_at)
        if not isinstance(self.state, PaymentState):
            self.state = PaymentState(str(self.state))
        if self.attempt_number < 1:
            raise InvariantViolationError("Payment attempt_number must be >= 1.")
        if not self.amount.is_positive():
            raise InvariantViolationError("Payment amount must be strictly positive.")
        if self.state == PaymentState.CAPTURED:
            self.failure = None

    @property
    def is_terminal(self) -> bool:
        """Check if payment has reached a terminal state."""
        return self.state in PAYMENT_TERMINAL_STATES

    def transition_to(
        self,
        new_state: PaymentState,
        occurred_at: datetime,
        failure: PaymentFailure | None = None,
        reason: str | None = None,
    ) -> None:
        """Perform a validated transition to a new PaymentState."""
        occurred_at = ensure_utc_datetime(occurred_at)
        if not isinstance(new_state, PaymentState):
            new_state = PaymentState(str(new_state))

        if self.state == new_state:
            return

        if self.is_terminal:
            raise TerminalStateError(
                aggregate_type="Payment",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason="Cannot mutate payment from terminal state.",
            )

        allowed = ALLOWED_PAYMENT_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                aggregate_type="Payment",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason=reason,
            )

        if new_state == PaymentState.FAILED and failure is not None:
            self.failure = failure
        elif new_state == PaymentState.CAPTURED:
            self.failure = None

        self.state = new_state
        self.updated_at = occurred_at

    def mark_pending(self, occurred_at: datetime) -> None:
        self.transition_to(PaymentState.PENDING, occurred_at)

    def mark_authorized(self, occurred_at: datetime) -> None:
        self.transition_to(PaymentState.AUTHORIZED, occurred_at)

    def capture(self, occurred_at: datetime) -> None:
        self.transition_to(PaymentState.CAPTURED, occurred_at)

    def fail(self, failure: PaymentFailure, occurred_at: datetime) -> None:
        self.transition_to(PaymentState.FAILED, occurred_at, failure=failure)

    def cancel(self, occurred_at: datetime, reason: str | None = None) -> None:
        self.transition_to(PaymentState.CANCELLED, occurred_at, reason=reason)

    def refund(self, occurred_at: datetime, is_partial: bool = False) -> None:
        new_state = PaymentState.PARTIALLY_REFUNDED if is_partial else PaymentState.REFUNDED
        self.transition_to(new_state, occurred_at)
