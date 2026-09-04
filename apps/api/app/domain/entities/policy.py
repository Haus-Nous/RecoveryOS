"""Merchant policy aggregate establishing deterministic guardrails."""

from dataclasses import dataclass
from datetime import datetime

from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.exceptions import InvalidPolicyError
from app.domain.types import MerchantId, PolicyId, ensure_utc_datetime
from app.domain.values.money import Money


@dataclass(slots=True)
class Policy:
    """Merchant-configured authorization guardrails."""

    id: PolicyId
    merchant_id: MerchantId
    enabled: bool
    max_retry_attempts: int
    cooldown_seconds: int
    auto_action_amount_limit: Money
    review_required_above: Money
    allowed_strategies: frozenset[RecoveryStrategy]
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        self.created_at = ensure_utc_datetime(self.created_at)
        self.updated_at = ensure_utc_datetime(self.updated_at)
        if self.max_retry_attempts < 0:
            raise InvalidPolicyError("Policy max_retry_attempts must be >= 0.")
        if self.cooldown_seconds < 0:
            raise InvalidPolicyError("Policy cooldown_seconds must be >= 0.")
        if self.auto_action_amount_limit.currency != self.review_required_above.currency:
            raise InvalidPolicyError("Policy amount thresholds must have the same currency.")
        if self.auto_action_amount_limit > self.review_required_above:
            raise InvalidPolicyError(
                "Policy auto_action_amount_limit cannot exceed review_required_above."
            )
