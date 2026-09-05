"""Tests verifying complete explicit coverage and behavior of all 22 laboratory scenarios."""

import random
from datetime import UTC, datetime

import pytest

from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.lab.scenarios.base import ScenarioContext
from app.lab.scenarios.catalog import SCENARIO_CATALOG
from app.lab.types import (
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticFailureCategory,
)


@pytest.mark.parametrize("scenario_id", sorted(SCENARIO_CATALOG.keys()))
def test_all_22_scenarios_generate_valid_domain_journeys(scenario_id: str) -> None:
    """Explicitly verify every single scenario definition, method constraints, and lifecycle."""
    scenario_def = SCENARIO_CATALOG[scenario_id]
    assert scenario_def.scenario_id == scenario_id
    assert scenario_def.default_weight_bps > 0

    rng = random.Random(42)
    method = next(iter(scenario_def.allowed_methods))
    amount = Money.from_minor(2500_00, Currency.INR)
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    ctx = ScenarioContext(
        journey_id=f"jny_test_{scenario_id}",
        order_id=f"ord_test_{scenario_id}",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=amount,
        currency=Currency.INR,
        payment_method=method,
        anchor_time=t0,
        rng=rng,
        labels_version="1.0.0",
    )

    journey, events, gt = scenario_def.generator_fn(ctx)

    # 1. Output structure checks
    assert journey.journey_id == ctx.journey_id
    assert journey.merchant_id == ctx.merchant_id
    assert journey.amount_in_cents == 2500_00
    assert len(events) >= 2
    assert len(journey.observed_event_ids) == len(events)

    # 2. Ground Truth alignment
    assert gt.scenario_id == scenario_id
    assert gt.merchant_id == ctx.merchant_id
    assert gt.recoverability == scenario_def.recoverability
    assert gt.expected_recovery_strategy_class == scenario_def.expected_strategy
    assert len(gt.attempt_truths) == gt.expected_number_of_attempts
    assert len(journey.payment_ids) == gt.expected_number_of_attempts

    # 3. Multi-attempt ground truth checks
    for idx, att in enumerate(gt.attempt_truths, start=1):
        assert att.attempt_number == idx
        assert att.payment_id in journey.payment_ids
        assert att.expected_final_state in ("CAPTURED", "FAILED")
        if att.expected_final_state == "CAPTURED":
            assert att.failure_category == SyntheticFailureCategory.NONE
            assert att.recoverability == Recoverability.NOT_APPLICABLE
        else:
            assert att.failure_category != SyntheticFailureCategory.NONE


def test_scenario_method_incompatibility_raises_error() -> None:
    """Incompatible payment method choice must fail fast."""
    s09_card_only = SCENARIO_CATALOG["S09"]
    with pytest.raises(ValueError, match="not supported by scenario S09"):
        s09_card_only.validate_method_compatibility(PaymentMethod.UPI)

    s21_upi_only = SCENARIO_CATALOG["S21"]
    with pytest.raises(ValueError, match="not supported by scenario S21"):
        s21_upi_only.validate_method_compatibility(PaymentMethod.CARD)


def test_amendment_semantics_alignment() -> None:
    """Verify specific semantic adjustments mandated in review amendments."""
    # S05: Timeout with underlying success
    s05 = SCENARIO_CATALOG["S05"]
    assert s05.recoverability == Recoverability.NOT_APPLICABLE
    assert s05.expected_strategy == RecoveryStrategyClass.NO_RECOVERY_NEEDED

    # S17: Late asynchronous success
    s17 = SCENARIO_CATALOG["S17"]
    assert s17.recoverability == Recoverability.NOT_APPLICABLE
    assert s17.expected_strategy == RecoveryStrategyClass.NO_RECOVERY_NEEDED

    # S04: Insufficient funds permanent
    s04 = SCENARIO_CATALOG["S04"]
    assert s04.recoverability == Recoverability.NON_RECOVERABLE
    assert s04.expected_strategy == RecoveryStrategyClass.DO_NOT_RETRY

    # S08: Authentication abandonment
    s08 = SCENARIO_CATALOG["S08"]
    assert s08.recoverability == Recoverability.NON_RECOVERABLE
    assert s08.expected_strategy == RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED

    # S21: Uses NETWORK_TIMEOUT taxonomy
    s21 = SCENARIO_CATALOG["S21"]
    assert s21.failure_category == SyntheticFailureCategory.NETWORK_TIMEOUT
