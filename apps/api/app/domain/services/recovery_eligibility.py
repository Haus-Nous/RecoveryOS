"""Pure domain service for determining payment recovery eligibility."""

from app.domain.entities.payment import Payment, PaymentState
from app.domain.values.failure import FailureCategory


def check_recovery_eligibility(payment: Payment) -> tuple[bool, str | None]:
    """Evaluate pure domain eligibility of a payment attempt for opening a RecoveryCase.

    Returns:
        tuple[bool, str | None]: (is_eligible, reason_if_ineligible)
    """
    if payment.state != PaymentState.FAILED:
        return (
            False,
            f"Payment is '{payment.state.value}'; only FAILED payments can open recovery case.",
        )

    if not payment.amount.is_positive():
        return False, "Payment amount must be strictly positive to open a recovery case."

    if (
        payment.failure
        and payment.failure.category == FailureCategory.HARD_DECLINE
        and not payment.failure.is_retryable_hint
    ):
        return False, "Payment suffered a non-retryable HARD_DECLINE."

    return True, None
