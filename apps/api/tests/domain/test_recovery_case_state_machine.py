"""Tests for RecoveryCase aggregate and transition matrix."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.recovery_case import (
    ALLOWED_CASE_TRANSITIONS,
    CASE_TERMINAL_STATES,
    RecoveryCase,
    RecoveryCaseState,
)
from app.domain.exceptions import (
    InvalidStateTransitionError,
    InvariantViolationError,
    TerminalStateError,
)
from app.domain.types import MerchantId, PaymentId, RecoveryCaseId
from app.domain.values.currency import Currency
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def create_case(state: RecoveryCaseState = RecoveryCaseState.OPEN) -> RecoveryCase:
    return RecoveryCase(
        id=RecoveryCaseId("rc_123"),
        merchant_id=MerchantId("mer_abc"),
        payment_id=PaymentId("pay_123"),
        amount_at_risk=Money.from_minor(10000, Currency.INR),
        state=state,
        opened_at=NOW,
        updated_at=NOW,
    )


class TestRecoveryCaseStateMachine:
    def test_full_recovery_lifecycle(self) -> None:
        case = create_case(RecoveryCaseState.OPEN)
        case.transition_to(RecoveryCaseState.DIAGNOSING, NOW)
        case.transition_to(RecoveryCaseState.PLANNED, NOW)
        case.transition_to(RecoveryCaseState.APPROVED, NOW)
        case.transition_to(RecoveryCaseState.EXECUTING, NOW)
        case.transition_to(
            RecoveryCaseState.RECOVERED,
            NOW,
            reason="Payment successfully recaptured",
        )

        assert case.state == RecoveryCaseState.RECOVERED
        assert case.is_terminal
        assert case.terminal_reason == "Payment successfully recaptured"

    def test_exhausted_lifecycle(self) -> None:
        case = create_case(RecoveryCaseState.OPEN)
        case.transition_to(RecoveryCaseState.DIAGNOSING, NOW)
        case.transition_to(RecoveryCaseState.EXHAUSTED, NOW, reason="Max retries reached")
        assert case.state == RecoveryCaseState.EXHAUSTED
        assert case.is_terminal

    def test_terminal_case_rejects_reopen(self) -> None:
        case = create_case(RecoveryCaseState.RECOVERED)
        with pytest.raises(TerminalStateError):
            case.transition_to(RecoveryCaseState.OPEN, NOW)

        with pytest.raises(TerminalStateError):
            case.transition_to(RecoveryCaseState.DIAGNOSING, NOW)

    def test_amount_at_risk_must_be_positive(self) -> None:
        with pytest.raises(InvariantViolationError):
            RecoveryCase(
                id=RecoveryCaseId("rc_123"),
                merchant_id=MerchantId("mer_abc"),
                payment_id=PaymentId("pay_123"),
                amount_at_risk=Money.zero(Currency.INR),
                state=RecoveryCaseState.OPEN,
                opened_at=NOW,
                updated_at=NOW,
            )

    @pytest.mark.parametrize("from_state", list(RecoveryCaseState))
    @pytest.mark.parametrize("to_state", list(RecoveryCaseState))
    def test_complete_case_transition_matrix(
        self, from_state: RecoveryCaseState, to_state: RecoveryCaseState
    ) -> None:
        case = create_case(from_state)
        is_allowed = to_state in ALLOWED_CASE_TRANSITIONS[from_state]

        if from_state == to_state:
            case.transition_to(to_state, NOW)
            assert case.state == from_state
        elif is_allowed:
            case.transition_to(to_state, NOW)
            assert case.state == to_state
        else:
            if from_state in CASE_TERMINAL_STATES:
                with pytest.raises(TerminalStateError):
                    case.transition_to(to_state, NOW)
            else:
                with pytest.raises(InvalidStateTransitionError):
                    case.transition_to(to_state, NOW)
