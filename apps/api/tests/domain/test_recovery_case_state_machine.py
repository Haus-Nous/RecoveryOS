"""Tests for RecoveryCase aggregate and full 13-state verification lifecycle matrix."""

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
    def test_full_verified_recovery_lifecycle(self) -> None:
        """Full happy path through observed recovery and ledger verification."""
        case = create_case(RecoveryCaseState.OPEN)
        assert not case.is_terminal

        case.transition_to(RecoveryCaseState.DIAGNOSING, NOW)
        case.transition_to(RecoveryCaseState.PLANNED, NOW)
        case.transition_to(RecoveryCaseState.APPROVED, NOW)
        case.transition_to(RecoveryCaseState.EXECUTING, NOW)

        # Recovery observed from gateway/customer action
        case.transition_to(RecoveryCaseState.RECOVERY_OBSERVED, NOW)
        assert not case.is_terminal

        # Queued for settlement/ledger verification
        case.transition_to(RecoveryCaseState.AWAITING_VERIFICATION, NOW)
        assert not case.is_terminal

        # Verified by ledger reconciliation
        case.transition_to(
            RecoveryCaseState.VERIFIED_RECOVERED,
            NOW,
            reason="Settlement batch matched payout evidence",
        )
        assert case.state == RecoveryCaseState.VERIFIED_RECOVERED
        assert case.is_terminal
        assert case.terminal_reason == "Settlement batch matched payout evidence"

    def test_verification_failure_and_remediation_cycle(self) -> None:
        """Lifecycle handling verification failure and re-diagnosis."""
        case1 = create_case(RecoveryCaseState.RECOVERY_OBSERVED)
        case1.transition_to(RecoveryCaseState.AWAITING_VERIFICATION, NOW)

        # Settlement verification failed
        case1.transition_to(
            RecoveryCaseState.VERIFICATION_FAILED,
            NOW,
            reason="Settlement amount discrepancy detected",
        )
        assert case1.state == RecoveryCaseState.VERIFICATION_FAILED
        assert not case1.is_terminal

        # Re-diagnose or escalate from failure
        case2 = create_case(RecoveryCaseState.VERIFICATION_FAILED)
        case2.transition_to(RecoveryCaseState.DIAGNOSING, NOW)
        assert case2.state == RecoveryCaseState.DIAGNOSING

    def test_verification_failure_and_escalation_cycle(self) -> None:
        """Lifecycle handling verification failure: VERIFICATION_FAILED -> ESCALATED."""
        case = create_case(RecoveryCaseState.VERIFICATION_FAILED)
        case.transition_to(
            RecoveryCaseState.ESCALATED,
            NOW,
            reason="Manual operator review required",
        )
        assert case.state == RecoveryCaseState.ESCALATED
        assert not case.is_terminal

    def test_exhausted_lifecycle(self) -> None:
        case = create_case(RecoveryCaseState.OPEN)
        case.transition_to(RecoveryCaseState.DIAGNOSING, NOW)
        case.transition_to(RecoveryCaseState.EXHAUSTED, NOW, reason="Max retries reached")
        assert case.state == RecoveryCaseState.EXHAUSTED
        assert case.is_terminal

    def test_terminal_case_rejects_reopen(self) -> None:
        case = create_case(RecoveryCaseState.VERIFIED_RECOVERED)
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
        """Exhaustively verify all 13 x 13 = 169 RecoveryCase state transition pairs."""
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
