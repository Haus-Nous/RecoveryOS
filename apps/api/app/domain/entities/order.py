"""Order aggregate and state machine."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.exceptions import (
    InvalidStateTransitionError,
    InvariantViolationError,
    TerminalStateError,
)
from app.domain.types import MerchantId, OrderId, ensure_utc_datetime
from app.domain.values.money import Money


class OrderStatus(StrEnum):
    """Lifecycle states of a commercial checkout order."""

    CREATED = "CREATED"
    OPEN = "OPEN"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset({OrderStatus.OPEN, OrderStatus.CANCELLED}),
    OrderStatus.OPEN: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset(),  # Terminal
    OrderStatus.CANCELLED: frozenset(),  # Terminal
}

ORDER_TERMINAL_STATES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.PAID,
        OrderStatus.CANCELLED,
    }
)


@dataclass(slots=True)
class Order:
    """Canonical commercial checkout order aggregate."""

    id: OrderId
    merchant_id: MerchantId
    amount: Money
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    external_reference: str | None = None

    def __post_init__(self) -> None:
        self.created_at = ensure_utc_datetime(self.created_at)
        self.updated_at = ensure_utc_datetime(self.updated_at)
        if not isinstance(self.status, OrderStatus):
            self.status = OrderStatus(str(self.status))
        if not self.amount.is_positive():
            raise InvariantViolationError("Order amount must be strictly positive.")

    @property
    def is_terminal(self) -> bool:
        """Check if order has reached a terminal state."""
        return self.status in ORDER_TERMINAL_STATES

    def transition_to(
        self,
        new_status: OrderStatus,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> None:
        """Perform a validated transition to a new OrderStatus."""
        occurred_at = ensure_utc_datetime(occurred_at)
        if not isinstance(new_status, OrderStatus):
            new_status = OrderStatus(str(new_status))

        if self.status == new_status:
            return

        if self.is_terminal:
            raise TerminalStateError(
                aggregate_type="Order",
                aggregate_id=str(self.id),
                from_state=self.status.value,
                to_state=new_status.value,
                reason="Cannot mutate order from terminal state.",
            )

        allowed = ALLOWED_ORDER_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                aggregate_type="Order",
                aggregate_id=str(self.id),
                from_state=self.status.value,
                to_state=new_status.value,
                reason=reason,
            )

        self.status = new_status
        self.updated_at = occurred_at

    def mark_open(self, occurred_at: datetime) -> None:
        """Open order for incoming payment attempts."""
        self.transition_to(OrderStatus.OPEN, occurred_at)

    def mark_paid(self, occurred_at: datetime) -> None:
        """Mark order as settled in full."""
        self.transition_to(OrderStatus.PAID, occurred_at)

    def cancel(self, occurred_at: datetime, reason: str | None = None) -> None:
        """Cancel order."""
        self.transition_to(OrderStatus.CANCELLED, occurred_at, reason=reason)
