"""RecoveryAction aggregate and authorization guardrails."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.exceptions import (
    InvalidStateTransitionError,
    TerminalStateError,
    UnauthorizedActionTransitionError,
)
from app.domain.types import RecoveryActionId, RecoveryCaseId, ensure_utc_datetime
from app.domain.values.decision import PolicyDecision


class RecoveryActionState(StrEnum):
    """Lifecycle states of an executable recovery action."""

    PROPOSED = "PROPOSED"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    QUEUED = "QUEUED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_ACTION_TRANSITIONS: dict[RecoveryActionState, frozenset[RecoveryActionState]] = {
    RecoveryActionState.PROPOSED: frozenset(
        {
            RecoveryActionState.AWAITING_AUTHORIZATION,
            RecoveryActionState.AUTHORIZED,
            RecoveryActionState.DENIED,
            RecoveryActionState.CANCELLED,
        }
    ),
    RecoveryActionState.AWAITING_AUTHORIZATION: frozenset(
        {
            RecoveryActionState.AUTHORIZED,
            RecoveryActionState.DENIED,
            RecoveryActionState.CANCELLED,
        }
    ),
    RecoveryActionState.AUTHORIZED: frozenset(
        {
            RecoveryActionState.QUEUED,
            RecoveryActionState.EXECUTING,
            RecoveryActionState.CANCELLED,
        }
    ),
    RecoveryActionState.QUEUED: frozenset(
        {
            RecoveryActionState.EXECUTING,
            RecoveryActionState.CANCELLED,
        }
    ),
    RecoveryActionState.EXECUTING: frozenset(
        {
            RecoveryActionState.SUCCEEDED,
            RecoveryActionState.FAILED,
            RecoveryActionState.CANCELLED,
        }
    ),
    RecoveryActionState.DENIED: frozenset(),  # Terminal
    RecoveryActionState.SUCCEEDED: frozenset(),  # Terminal
    RecoveryActionState.FAILED: frozenset(),  # Terminal
    RecoveryActionState.CANCELLED: frozenset(),  # Terminal
}

ACTION_TERMINAL_STATES: frozenset[RecoveryActionState] = frozenset(
    {
        RecoveryActionState.DENIED,
        RecoveryActionState.SUCCEEDED,
        RecoveryActionState.FAILED,
        RecoveryActionState.CANCELLED,
    }
)


@dataclass(slots=True)
class RecoveryAction:
    """Executable unit representing an authorized recovery operation."""

    id: RecoveryActionId
    recovery_case_id: RecoveryCaseId
    strategy: RecoveryStrategy
    state: RecoveryActionState
    created_at: datetime
    updated_at: datetime
    authorization_decision: PolicyDecision | None = None
    authorization_reference: str | None = None
    attempt_number: int = 1
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        self.created_at = ensure_utc_datetime(self.created_at)
        self.updated_at = ensure_utc_datetime(self.updated_at)
        if not isinstance(self.state, RecoveryActionState):
            self.state = RecoveryActionState(str(self.state))
        if not isinstance(self.strategy, RecoveryStrategy):
            self.strategy = RecoveryStrategy(str(self.strategy))

        # CONSTRUCTOR INVARIANT: Cannot instantiate executable states without authorization
        if (
            self.state in (RecoveryActionState.QUEUED, RecoveryActionState.EXECUTING)
            and not self.is_authorized
        ):
            raise UnauthorizedActionTransitionError(
                f"RecoveryAction [{self.id}] cannot be initialized in '{self.state.value}' "
                f"without authorization (Current decision: {self.authorization_decision})."
            )

    @property
    def is_terminal(self) -> bool:
        return self.state in ACTION_TERMINAL_STATES

    @property
    def is_authorized(self) -> bool:
        return self.authorization_decision == PolicyDecision.ALLOW

    def authorize(self, decision: PolicyDecision, reference: str, occurred_at: datetime) -> None:
        """Record deterministic policy authorization."""
        occurred_at = ensure_utc_datetime(occurred_at)
        self.authorization_decision = decision
        self.authorization_reference = reference
        if decision == PolicyDecision.ALLOW:
            self.transition_to(RecoveryActionState.AUTHORIZED, occurred_at)
        elif decision == PolicyDecision.DENY:
            self.transition_to(RecoveryActionState.DENIED, occurred_at)
        elif decision == PolicyDecision.REVIEW:
            self.transition_to(RecoveryActionState.AWAITING_AUTHORIZATION, occurred_at)

    def transition_to(
        self,
        new_state: RecoveryActionState,
        occurred_at: datetime,
        reason: str | None = None,
    ) -> None:
        """Perform a validated transition enforcing the authorization guardrail invariant."""
        occurred_at = ensure_utc_datetime(occurred_at)
        if not isinstance(new_state, RecoveryActionState):
            new_state = RecoveryActionState(str(new_state))

        if self.state == new_state:
            return

        if self.is_terminal:
            raise TerminalStateError(
                aggregate_type="RecoveryAction",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason="Cannot mutate RecoveryAction from a terminal state.",
            )

        # CRITICAL INVARIANT: Cannot queue or execute without valid authorization
        if (
            new_state in (RecoveryActionState.QUEUED, RecoveryActionState.EXECUTING)
            and not self.is_authorized
        ):
            raise UnauthorizedActionTransitionError(
                f"RecoveryAction [{self.id}] cannot transition to '{new_state.value}' "
                f"without authorization (Current decision: {self.authorization_decision})."
            )

        allowed = ALLOWED_ACTION_TRANSITIONS.get(self.state, frozenset())
        if new_state not in allowed:
            raise InvalidStateTransitionError(
                aggregate_type="RecoveryAction",
                aggregate_id=str(self.id),
                from_state=self.state.value,
                to_state=new_state.value,
                reason=reason,
            )

        if new_state == RecoveryActionState.FAILED and reason:
            self.failure_reason = reason

        self.state = new_state
        self.updated_at = occurred_at
