"""Tests for Order aggregate and complete state machine matrix."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.order import (
    ALLOWED_ORDER_TRANSITIONS,
    ORDER_TERMINAL_STATES,
    Order,
    OrderStatus,
)
from app.domain.exceptions import (
    InvalidStateTransitionError,
    TerminalStateError,
)
from app.domain.types import MerchantId, OrderId
from app.domain.values.currency import Currency
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def create_order(status: OrderStatus = OrderStatus.CREATED) -> Order:
    return Order(
        id=OrderId("ord_123"),
        merchant_id=MerchantId("mer_abc"),
        amount=Money.from_minor(50000, Currency.INR),
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


class TestOrderStateMachine:
    def test_created_to_open_transition(self) -> None:
        order = create_order(OrderStatus.CREATED)
        assert not order.is_terminal
        order.mark_open(NOW)
        assert order.status == OrderStatus.OPEN
        assert not order.is_terminal

    def test_open_to_paid_transition(self) -> None:
        order = create_order(OrderStatus.OPEN)
        order.mark_paid(NOW)
        assert order.status == OrderStatus.PAID
        assert order.is_terminal

    def test_cancel_from_created(self) -> None:
        order = create_order(OrderStatus.CREATED)
        order.cancel(NOW, reason="Customer abandoned cart")
        assert order.status == OrderStatus.CANCELLED
        assert order.is_terminal

    def test_cancel_from_open(self) -> None:
        order = create_order(OrderStatus.OPEN)
        order.cancel(NOW, reason="Expired")
        assert order.status == OrderStatus.CANCELLED

    def test_terminal_paid_rejects_transitions(self) -> None:
        order = create_order(OrderStatus.PAID)
        with pytest.raises(TerminalStateError):
            order.transition_to(OrderStatus.OPEN, NOW)

        with pytest.raises(TerminalStateError):
            order.transition_to(OrderStatus.CANCELLED, NOW)

    def test_terminal_cancelled_rejects_transitions(self) -> None:
        order = create_order(OrderStatus.CANCELLED)
        with pytest.raises(TerminalStateError):
            order.transition_to(OrderStatus.PAID, NOW)

        with pytest.raises(TerminalStateError):
            order.transition_to(OrderStatus.OPEN, NOW)

    @pytest.mark.parametrize("from_status", list(OrderStatus))
    @pytest.mark.parametrize("to_status", list(OrderStatus))
    def test_complete_order_transition_matrix(
        self, from_status: OrderStatus, to_status: OrderStatus
    ) -> None:
        """Exhaustively test all N x N state transition pairs for Order."""
        order = create_order(from_status)
        is_allowed = to_status in ALLOWED_ORDER_TRANSITIONS[from_status]

        if from_status == to_status:
            order.transition_to(to_status, NOW)
            assert order.status == from_status
        elif is_allowed:
            order.transition_to(to_status, NOW)
            assert order.status == to_status
        else:
            if from_status in ORDER_TERMINAL_STATES:
                with pytest.raises(TerminalStateError):
                    order.transition_to(to_status, NOW)
            else:
                with pytest.raises(InvalidStateTransitionError):
                    order.transition_to(to_status, NOW)
