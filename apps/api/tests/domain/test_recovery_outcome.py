"""Tests for RecoveryOutcome, verifying action success != revenue recovered != verified revenue."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_outcome import (
    OutcomeStatus,
    RecoveryOutcome,
    VerificationStatus,
)
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.exceptions import VerificationInvariantError
from app.domain.types import RecoveryActionId, RecoveryCaseId
from app.domain.values.currency import Currency
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


class TestRecoveryOutcome:
    def test_action_success_is_distinct_from_verified_recovery(self) -> None:
        """CRITICAL INVARIANT TEST: Action Succeeded != Revenue Recovered != Verified Revenue."""
        action = RecoveryAction(
            id=RecoveryActionId("act_123"),
            recovery_case_id=RecoveryCaseId("rc_123"),
            strategy=RecoveryStrategy.RETRY_SAME_METHOD,
            state=RecoveryActionState.SUCCEEDED,
            created_at=NOW,
            updated_at=NOW,
        )
        assert action.state == RecoveryActionState.SUCCEEDED

        # 1. Action Succeeded but outcome is UNVERIFIED
        outcome = RecoveryOutcome(
            recovery_case_id=RecoveryCaseId("rc_123"),
            recovery_action_id=action.id,
            status=OutcomeStatus.RECOVERED,
            amount_recovered=Money.from_minor(10000, Currency.INR),
            observed_at=NOW,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        # Succeeded action with unverified outcome does NOT count as verified revenue
        assert not outcome.is_verified_revenue

        # 2. Reconciled and verified via evidence reference
        outcome.verify(verification_reference="SETTLE_PAYOUT_REF_999", verified_at=NOW)
        assert outcome.verification_status == VerificationStatus.VERIFIED
        assert outcome.is_verified_revenue

    def test_verified_status_without_evidence_reference_raises(self) -> None:
        """CRITICAL INVARIANT TEST: Cannot mark VERIFIED without reference evidence."""
        with pytest.raises(VerificationInvariantError):
            RecoveryOutcome(
                recovery_case_id=RecoveryCaseId("rc_123"),
                recovery_action_id=RecoveryActionId("act_123"),
                status=OutcomeStatus.RECOVERED,
                amount_recovered=Money.from_minor(5000, Currency.INR),
                observed_at=NOW,
                verification_status=VerificationStatus.VERIFIED,
                verification_reference=None,  # Missing evidence!
                verified_at=NOW,
            )

    def test_rejected_verification(self) -> None:
        outcome = RecoveryOutcome(
            recovery_case_id=RecoveryCaseId("rc_123"),
            recovery_action_id=RecoveryActionId("act_123"),
            status=OutcomeStatus.RECOVERED,
            amount_recovered=Money.from_minor(5000, Currency.INR),
            observed_at=NOW,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        outcome.reject_verification(
            reason="Chargeback detected prior to settlement",
            verified_at=NOW,
        )
        assert outcome.verification_status == VerificationStatus.REJECTED
        assert not outcome.is_verified_revenue
