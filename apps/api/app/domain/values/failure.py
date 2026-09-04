"""Payment failure taxonomy and structured failure context."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.types import ensure_utc_datetime


class FailureCategory(StrEnum):
    """Canonical provider-independent payment failure categories."""

    SOFT_DECLINE = "SOFT_DECLINE"
    HARD_DECLINE = "HARD_DECLINE"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    NETWORK_ERROR = "NETWORK_ERROR"
    BANK_UNAVAILABLE = "BANK_UNAVAILABLE"
    AUTHENTICATION_FAILURE = "AUTHENTICATION_FAILURE"
    MANDATE_FAILURE = "MANDATE_FAILURE"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    CUSTOMER_ABANDONMENT = "CUSTOMER_ABANDONMENT"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PaymentFailure:
    """Immutable structured failure detail for a failed payment attempt."""

    category: FailureCategory
    code: str | None
    reason: str
    is_retryable_hint: bool
    occurred_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", ensure_utc_datetime(self.occurred_at))
        if not isinstance(self.category, FailureCategory):
            object.__setattr__(self, "category", FailureCategory(str(self.category)))
        if not isinstance(self.reason, str) or not self.reason.strip():
            object.__setattr__(self, "reason", "Unknown payment failure reason")
