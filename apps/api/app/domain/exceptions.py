"""RecoveryOS Domain Exception Hierarchy.

Pure domain exceptions distinct from transport, ORM, or infrastructure errors.
"""

from typing import Any


class DomainError(Exception):
    """Base exception for all RecoveryOS domain rule and invariant violations."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidMoneyError(DomainError):
    """Raised when money is instantiated with invalid types (e.g. float) or negative amounts."""


class CurrencyMismatchError(DomainError):
    """Raised when attempting arithmetic or comparison across disparate currencies."""

    def __init__(self, currency_a: str, currency_b: str) -> None:
        super().__init__(
            f"Cannot perform monetary operation across mismatching currencies: "
            f"{currency_a} and {currency_b}",
            {"currency_a": currency_a, "currency_b": currency_b},
        )


class InvalidCurrencyError(DomainError):
    """Raised when an unsupported or malformed currency is specified."""


class InvalidTimestampError(DomainError):
    """Raised when a datetime is naive (missing timezone) or improperly formatted."""


class InvalidConfidenceError(DomainError):
    """Raised when a confidence score falls outside valid bounded limits [0, 10000] bps."""


class InvalidStateTransitionError(DomainError):
    """Raised when an illegal state transition is attempted on an entity or aggregate."""

    def __init__(
        self,
        aggregate_type: str,
        aggregate_id: str,
        from_state: str,
        to_state: str,
        reason: str | None = None,
    ) -> None:
        msg = (
            f"Illegal transition for {aggregate_type} [{aggregate_id}] "
            f"from '{from_state}' to '{to_state}'."
        )
        if reason:
            msg += f" Reason: {reason}"
        super().__init__(
            msg,
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
            },
        )


class TerminalStateError(InvalidStateTransitionError):
    """Raised when attempting any state mutation from a terminal state."""


class InvariantViolationError(DomainError):
    """Raised when a core domain invariant is breached."""


class UnauthorizedActionTransitionError(InvariantViolationError):
    """Raised when an action attempts to transition without prior authorization."""


class VerificationInvariantError(InvariantViolationError):
    """Raised when an outcome is marked VERIFIED without required reconciliation evidence."""


class InvalidPolicyError(DomainError):
    """Raised when policy limits, thresholds, or configuration are invalid."""
