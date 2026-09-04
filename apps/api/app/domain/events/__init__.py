"""Domain events package."""

from app.domain.events.base import DomainEvent
from app.domain.events.order_events import OrderCancelled, OrderCreated, OrderPaid
from app.domain.events.payment_events import (
    PaymentCaptured,
    PaymentCreated,
    PaymentFailed,
)
from app.domain.events.recovery_events import (
    RecoveryActionAuthorized,
    RecoveryActionDenied,
    RecoveryCaseOpened,
    RecoveryOutcomeRecorded,
    RecoveryProposalCreated,
    RecoveryVerified,
)

__all__ = [
    "DomainEvent",
    "OrderCancelled",
    "OrderCreated",
    "OrderPaid",
    "PaymentCaptured",
    "PaymentCreated",
    "PaymentFailed",
    "RecoveryActionAuthorized",
    "RecoveryActionDenied",
    "RecoveryCaseOpened",
    "RecoveryOutcomeRecorded",
    "RecoveryProposalCreated",
    "RecoveryVerified",
]
