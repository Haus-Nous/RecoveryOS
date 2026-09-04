"""Order lifecycle domain events."""

from datetime import datetime

from app.domain.events.base import DomainEvent
from app.domain.types import MerchantId, OrderId
from app.domain.values.money import Money


class OrderCreated(DomainEvent):
    """Fired when a new commercial order is initiated."""

    @classmethod
    def from_order(
        cls,
        order_id: OrderId,
        merchant_id: MerchantId,
        amount: Money,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="OrderCreated",
            aggregate_id=str(order_id),
            aggregate_type="Order",
            occurred_at=occurred_at,
            payload={
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
                "amount_minor": amount.amount_minor,
                "currency": amount.currency.value,
            },
        )


class OrderPaid(DomainEvent):
    """Fired when an order is settled in full."""

    @classmethod
    def from_order(
        cls,
        order_id: OrderId,
        merchant_id: MerchantId,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="OrderPaid",
            aggregate_id=str(order_id),
            aggregate_type="Order",
            occurred_at=occurred_at,
            payload={
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
            },
        )


class OrderCancelled(DomainEvent):
    """Fired when an order is cancelled."""

    @classmethod
    def from_order(
        cls,
        order_id: OrderId,
        merchant_id: MerchantId,
        reason: str | None,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="OrderCancelled",
            aggregate_id=str(order_id),
            aggregate_type="Order",
            occurred_at=occurred_at,
            payload={
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
                "reason": reason,
            },
        )
