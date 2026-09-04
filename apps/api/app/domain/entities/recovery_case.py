"""RecoveryCase aggregate and lifecycle state machine."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.exceptions import (
    InvalidStateTransitionError,
    InvariantViolationError,
    TerminalStateError,
)
from app.domain.types import (
    MerchantId,
    PaymentId,
    RecoveryCaseId,
    ensure_utc_datetime,
)
from app.domain.values.failure import PaymentFailure
from app.domain.values.money import Money


class RecoveryCaseState(StrEnum):
    """Lifecycle states of a revenue-loss recovery case."""

    OPEN = "OPEN"
    DIAGNOSING = "DIAGNOSING"
    PLANNED = "PLANNED"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RECOVERED = "RECOVERED"
    EXHAUSTED = "EXHAUSTED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


ALLOWED_CASE_TRANSITIONS: dict[RecoveryCaseState, frozenset[RecoveryCaseState]] = {
    RecoveryCaseState.OPEN: frozenset(
        {
            RecoveryCaseState.DIAGNOSING,
            RecoveryCaseState.CANCELLED,
        }
    ),
    RecoveryCaseState.DIAGNOSING: frozenset(
        {
            RecoveryCaseState.PLANNED,
            RecoveryCaseState.EXHAUSTED,
            RecoveryCaseState.CANCELLED,
        }
    ),
    RecoveryCaseState.PLANNED: frozenset(
        {
            RecoveryCaseState.AWAITING_REVIEW,
            RecoveryCaseState.APPROVED,
            RecoveryCaseState.EXHAUSTED,
            RecoveryCaseState.CANCELLED,
        }
    ),
    RecoveryCaseState.AWAITING_REVIEW: frozenset(
        {
            RecoveryCaseState.APPROVED,
            RecoveryCaseState.CANCELLED,
            RecoveryCaseState.EXHAUSTED,
        }
    ),
    RecoveryCaseState.APPROVED: frozenset(
        {
            RecoveryCaseState.EXECUTING,
            RecoveryCaseState.CANCELLED,
        }
    ),
    RecoveryCaseState.EXECUTING: frozenset(
        {
            RecoveryCaseState.RECOVERED,
            RecoveryCaseState.DIAGNOSING,
            RecoveryCaseState.PLANNED,
            RecoveryCaseState.EXHAUSTED,
            RecoveryCaseState.ESCALATED,
        }
    ),
    RecoveryCaseState.ESCALATED: frozenset(
        {
            RecoveryCaseState.PLANNED,
            RecoveryCaseState.EXHAUSTED,
            RecoveryCaseState.CANCELLED,
        }
    ),
    RecoveryCaseState.RECOVERED: frozenset(),  # Terminal
    RecoveryCaseState.EXHAUSTED: frozenset(),  # Terminal
    RecoveryCaseState.CANCELLED: frozenset(),  # Terminal
}

CASE_TERMINAL_STATES: frozenset[RecoveryCaseState] = frozenset(
    {
        RecoveryCaseState.RECOVERED,
        RecoveryCaseState.EXHAUSTED,
        RecoveryCaseState.CANCELLED,
    }
)


@dataclass(slots=True)
class RecoveryCase:
    """Represents a discrete unit of lost revenue undergoing recovery investigation."""

    id: RecoveryCaseId
    merchant_id: MerchantId
    payment_id: PaymentId
    amount_at_risk: Money
    state: RecoveryCaseState
    opened_at: datetime
    updated_at: datetime
    failure_context: PaymentFailure | None = None
    attempt_count: int = 0
    terminal_reason: str | None = None

    def __post_init__(self) -> None:
        self.opened_at = ensure_utc_datetime(self.opened_at)
        self.updated_at = ensure_utc_datetime(self.updated_at)
        if not isinstance(self.state, RecoveryCaseState):
            self.state = RecoveryCaseState(str(self.state))
        if not self.amount_at_risk.is_positive():
            raise InvariantViolationError("RecoveryCase amount_at_risk must be strictly positive.")
        if self.attempt_count < 0:
            raise InvariantViolationError("RecoveryCase attempt_count cannot be negative.")

    @property
    def is_terminal(self) -> bool:
        return self.state in CASE_TERMINAL_STATES

    def transition_to(
        self,
        new_state: RecoveryCaseState,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> None:
        """Execute a validated transition to a new RecoveryCaseState."""
        occurred_at = ensure_utc_datetime(occurred_at)
        if not isinstance(new_state, RecoveryCaseState):
            new_state = RecoveryCaseState(str(new_state))

        if self.state == new_state:
            return

        if self.is_terminal:
            raise TerminalStateError(
                aggregate_type="RecoveryCase",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason="Cannot mutate RecoveryCase from a terminal state.",
            )

        allowed = ALLOWED_CASE_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                aggregate_type="RecoveryCase",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason=reason,
            )

        if new_state in CASE_TERMINAL_STATES and reason:
            self.terminal_reason = reason

        self.state = new_state
        self.updated_at = occurred_at
