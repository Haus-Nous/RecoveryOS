"""Domain entities and aggregates package."""

from app.domain.entities.order import (
    ALLOWED_ORDER_TRANSITIONS,
    ORDER_TERMINAL_STATES,
    Order,
    OrderStatus,
)
from app.domain.entities.payment import (
    ALLOWED_PAYMENT_TRANSITIONS,
    PAYMENT_TERMINAL_STATES,
    Payment,
    PaymentState,
)
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_action import (
    ACTION_TERMINAL_STATES,
    ALLOWED_ACTION_TRANSITIONS,
    RecoveryAction,
    RecoveryActionState,
)
from app.domain.entities.recovery_case import (
    ALLOWED_CASE_TRANSITIONS,
    CASE_TERMINAL_STATES,
    RecoveryCase,
    RecoveryCaseState,
)
from app.domain.entities.recovery_outcome import (
    OutcomeStatus,
    RecoveryOutcome,
    VerificationStatus,
)
from app.domain.entities.recovery_proposal import (
    RecoveryProposal,
    RecoveryStrategy,
)

__all__ = [
    "ACTION_TERMINAL_STATES",
    "ALLOWED_ACTION_TRANSITIONS",
    "ALLOWED_CASE_TRANSITIONS",
    "ALLOWED_ORDER_TRANSITIONS",
    "ALLOWED_PAYMENT_TRANSITIONS",
    "CASE_TERMINAL_STATES",
    "ORDER_TERMINAL_STATES",
    "PAYMENT_TERMINAL_STATES",
    "Order",
    "OrderStatus",
    "OutcomeStatus",
    "Payment",
    "PaymentState",
    "Policy",
    "RecoveryAction",
    "RecoveryActionState",
    "RecoveryCase",
    "RecoveryCaseState",
    "RecoveryOutcome",
    "RecoveryProposal",
    "RecoveryStrategy",
    "VerificationStatus",
]
