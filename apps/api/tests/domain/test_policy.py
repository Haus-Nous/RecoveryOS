"""Tests for Policy aggregate and merchant guardrails."""

from datetime import UTC, datetime

import pytest

from app.domain.entities.policy import Policy
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.exceptions import InvalidPolicyError
from app.domain.types import MerchantId, PolicyId
from app.domain.values.currency import Currency
from app.domain.values.money import Money

NOW = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)


def test_valid_policy() -> None:
    policy = Policy(
        id=PolicyId("pol_123"),
        merchant_id=MerchantId("mer_abc"),
        enabled=True,
        max_retry_attempts=3,
        cooldown_seconds=300,
        auto_action_amount_limit=Money.from_minor(25000, Currency.INR),
        review_required_above=Money.from_minor(50000, Currency.INR),
        allowed_strategies=frozenset(
            {
                RecoveryStrategy.RETRY_SAME_METHOD,
                RecoveryStrategy.CREATE_PAYMENT_LINK,
            }
        ),
        created_at=NOW,
        updated_at=NOW,
    )
    assert policy.enabled
    assert policy.max_retry_attempts == 3
    assert policy.auto_action_amount_limit.amount_minor == 25000


def test_negative_retry_limit_raises() -> None:
    with pytest.raises(InvalidPolicyError):
        Policy(
            id=PolicyId("pol_123"),
            merchant_id=MerchantId("mer_abc"),
            enabled=True,
            max_retry_attempts=-1,
            cooldown_seconds=300,
            auto_action_amount_limit=Money.from_minor(1000, Currency.INR),
            review_required_above=Money.from_minor(5000, Currency.INR),
            allowed_strategies=frozenset(),
            created_at=NOW,
            updated_at=NOW,
        )


def test_currency_mismatch_in_policy_limits_raises() -> None:
    with pytest.raises(InvalidPolicyError):
        Policy(
            id=PolicyId("pol_123"),
            merchant_id=MerchantId("mer_abc"),
            enabled=True,
            max_retry_attempts=3,
            cooldown_seconds=300,
            auto_action_amount_limit=Money.from_minor(1000, Currency.INR),
            review_required_above=Money.from_minor(5000, Currency.USD),
            allowed_strategies=frozenset(),
            created_at=NOW,
            updated_at=NOW,
        )
