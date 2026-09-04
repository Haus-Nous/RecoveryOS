"""RecoveryOutcome representing observed results and verification state.

CRITICAL INVARIANT:
Action Succeeded != Revenue Recovered (Observed) != Verified Recovered Revenue.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.exceptions import InvariantViolationError, VerificationInvariantError
from app.domain.types import RecoveryActionId, RecoveryCaseId, ensure_utc_datetime
from app.domain.values.money import Money


class OutcomeStatus(StrEnum):
    """Observed result of a recovery action prior to ledger verification."""

    NO_EFFECT = "NO_EFFECT"
    RECOVERY_OBSERVED = "RECOVERY_OBSERVED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class VerificationStatus(StrEnum):
    """Financial reconciliation verification status."""

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


@dataclass(slots=True)
class RecoveryOutcome:
    """Observed result and reconciliation verification state for a recovery attempt."""

    recovery_case_id: RecoveryCaseId
    recovery_action_id: RecoveryActionId
    status: OutcomeStatus
    amount_recovered: Money
    observed_at: datetime
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_reference: str | None = None
    verified_at: datetime | None = None

    def __post_init__(self) -> None:
        self.observed_at = ensure_utc_datetime(self.observed_at)
        if self.verified_at is not None:
            self.verified_at = ensure_utc_datetime(self.verified_at)
        if not isinstance(self.status, OutcomeStatus):
            self.status = OutcomeStatus(str(self.status))
        if not isinstance(self.verification_status, VerificationStatus):
            self.verification_status = VerificationStatus(str(self.verification_status))
        if self.amount_recovered.is_negative():
            raise InvariantViolationError("RecoveryOutcome amount_recovered cannot be negative.")

        # INVARIANT: VERIFIED requires evidence and timestamp
        if self.verification_status == VerificationStatus.VERIFIED:
            if self.status != OutcomeStatus.RECOVERY_OBSERVED:
                raise VerificationInvariantError(
                    "RecoveryOutcome cannot be VERIFIED if status is not RECOVERY_OBSERVED."
                )
            if not self.verification_reference or not self.verification_reference.strip():
                raise VerificationInvariantError(
                    "RecoveryOutcome cannot be VERIFIED without a valid verification_reference."
                )
            if self.verified_at is None:
                raise VerificationInvariantError(
                    "RecoveryOutcome cannot be VERIFIED without verified_at timestamp."
                )

    def verify(self, verification_reference: str, verified_at: datetime) -> None:
        """Mark observed recovery as verified via settlement/reconciliation evidence."""
        if self.status != OutcomeStatus.RECOVERY_OBSERVED:
            raise VerificationInvariantError(
                "Cannot verify outcome where recovery was not observed."
            )
        if not verification_reference or not verification_reference.strip():
            raise VerificationInvariantError("Verification evidence reference must be non-empty.")
        verified_at = ensure_utc_datetime(verified_at)

        self.verification_status = VerificationStatus.VERIFIED
        self.verification_reference = verification_reference.strip()
        self.verified_at = verified_at

    def reject_verification(self, reason: str, verified_at: datetime) -> None:
        """Mark reconciliation verification as rejected (e.g. settlement discrepancy)."""
        if not reason or not reason.strip():
            raise VerificationInvariantError("Rejection reason must be non-empty.")
        verified_at = ensure_utc_datetime(verified_at)
        self.verification_status = VerificationStatus.REJECTED
        self.verification_reference = reason.strip()
        self.verified_at = verified_at

    @property
    def is_verified_revenue(self) -> bool:
        """Return True ONLY if revenue is genuinely recovered AND verified by ledger."""
        return (
            self.status == OutcomeStatus.RECOVERY_OBSERVED
            and self.verification_status == VerificationStatus.VERIFIED
            and self.amount_recovered.is_positive()
        )
