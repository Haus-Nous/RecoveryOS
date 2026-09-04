"""Tests for RecoveryAction aggregate and mandatory authorization guardrails."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.recovery_action import (
    ACTION_TERMINAL_STATES,
    ALLOWED_ACTION_TRANSITIONS,
    RecoveryAction,
    RecoveryActionState,
)
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.exceptions import (
    InvalidStateTransitionError,
    TerminalStateError,
    UnauthorizedActionTransitionError,
)
from app.domain.types import RecoveryActionId, RecoveryCaseId
from app.domain.values.decision import PolicyDecision

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def create_action(state: RecoveryActionState = RecoveryActionState.PROPOSED) -> RecoveryAction:
    return RecoveryAction(
        id=RecoveryActionId("act_123"),
        recovery_case_id=RecoveryCaseId("rc_123"),
        strategy=RecoveryStrategy.RETRY_SAME_METHOD,
        state=state,
        created_at=NOW,
        updated_at=NOW,
    )


class TestRecoveryActionStateMachine:
    def test_authorized_action_can_execute_and_succeed(self) -> None:
        action = create_action(RecoveryActionState.PROPOSED)
        assert not action.is_authorized

        # Authorize action via policy ALLOW
        action.authorize(PolicyDecision.ALLOW, reference="POL_RULE_001", occurred_at=NOW)
        assert action.state == RecoveryActionState.AUTHORIZED
        assert action.is_authorized

        # Transition to QUEUED then EXECUTING then SUCCEEDED
        action.transition_to(RecoveryActionState.QUEUED, NOW)
        assert action.state == RecoveryActionState.QUEUED

        action.transition_to(RecoveryActionState.EXECUTING, NOW)
        assert action.state == RecoveryActionState.EXECUTING

        action.transition_to(RecoveryActionState.SUCCEEDED, NOW)
        assert action.state == RecoveryActionState.SUCCEEDED
        assert action.is_terminal

    def test_unauthorized_action_cannot_queue_or_execute(self) -> None:
        """CRITICAL INVARIANT TEST: Action cannot execute without authorization."""
        action = create_action(RecoveryActionState.PROPOSED)
        assert not action.is_authorized

        with pytest.raises(UnauthorizedActionTransitionError):
            action.transition_to(RecoveryActionState.QUEUED, NOW)

        with pytest.raises(UnauthorizedActionTransitionError):
            action.transition_to(RecoveryActionState.EXECUTING, NOW)

    def test_denied_action_cannot_execute(self) -> None:
        """CRITICAL INVARIANT TEST: Denied actions cannot execute."""
        action = create_action(RecoveryActionState.PROPOSED)
        action.authorize(PolicyDecision.DENY, reference="POL_LIMIT_EXCEEDED", occurred_at=NOW)
        assert action.state == RecoveryActionState.DENIED
        assert action.is_terminal

        with pytest.raises(TerminalStateError):
            action.transition_to(RecoveryActionState.QUEUED, NOW)

        with pytest.raises(TerminalStateError):
            action.transition_to(RecoveryActionState.EXECUTING, NOW)

    @pytest.mark.parametrize("from_state", list(RecoveryActionState))
    @pytest.mark.parametrize("to_state", list(RecoveryActionState))
    def test_complete_action_transition_matrix(
        self, from_state: RecoveryActionState, to_state: RecoveryActionState
    ) -> None:
        action = create_action(from_state)
        # Give authorization context if starting from AUTHORIZED or QUEUED
        authorized_states = (
            RecoveryActionState.AUTHORIZED,
            RecoveryActionState.QUEUED,
            RecoveryActionState.EXECUTING,
        )
        if from_state in authorized_states:
            action.authorization_decision = PolicyDecision.ALLOW

        is_allowed = to_state in ALLOWED_ACTION_TRANSITIONS[from_state]

        if from_state == to_state:
            action.transition_to(to_state, NOW)
            assert action.state == from_state
        elif is_allowed:
            action.transition_to(to_state, NOW)
            assert action.state == to_state
        else:
            if from_state in ACTION_TERMINAL_STATES:
                with pytest.raises(TerminalStateError):
                    action.transition_to(to_state, NOW)
            else:
                with pytest.raises(
                    (InvalidStateTransitionError, UnauthorizedActionTransitionError)
                ):
                    action.transition_to(to_state, NOW)
