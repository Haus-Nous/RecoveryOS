"""Payment attempt domain events."""

from datetime import datetime

from app.domain.events.base import DomainEvent
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.failure import PaymentFailure
from app.domain.values.money import Money


class PaymentCreated(DomainEvent):
    """Fired when a payment attempt is initialized."""

    @classmethod
    def from_payment(
        cls,
        payment_id: PaymentId,
        order_id: OrderId,
        merchant_id: MerchantId,
        amount: Money,
        attempt_number: int,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="PaymentCreated",
            aggregate_id=str(payment_id),
            aggregate_type="Payment",
            occurred_at=occurred_at,
            payload={
                "payment_id": str(payment_id),
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
                "amount_minor": amount.amount_minor,
                "currency": amount.currency.value,
                "attempt_number": attempt_number,
            },
        )


class PaymentFailed(DomainEvent):
    """Fired when a payment attempt fails or is declined."""

    @classmethod
    def from_payment(
        cls,
        payment_id: PaymentId,
        order_id: OrderId,
        merchant_id: MerchantId,
        failure: PaymentFailure,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="PaymentFailed",
            aggregate_id=str(payment_id),
            aggregate_type="Payment",
            occurred_at=occurred_at,
            payload={
                "payment_id": str(payment_id),
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
                "failure_category": failure.category.value,
                "failure_code": failure.code,
                "failure_reason": failure.reason,
                "is_retryable_hint": failure.is_retryable_hint,
            },
        )


class PaymentCaptured(DomainEvent):
    """Fired when payment funds are captured successfully."""

    @classmethod
    def from_payment(
        cls,
        payment_id: PaymentId,
        order_id: OrderId,
        merchant_id: MerchantId,
        amount: Money,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="PaymentCaptured",
            aggregate_id=str(payment_id),
            aggregate_type="Payment",
            occurred_at=occurred_at,
            payload={
                "payment_id": str(payment_id),
                "order_id": str(order_id),
                "merchant_id": str(merchant_id),
                "amount_minor": amount.amount_minor,
                "currency": amount.currency.value,
            },
        )
