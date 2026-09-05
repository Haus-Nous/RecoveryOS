"""Tests verifying event transport anomalies and decoupling from true economic lifecycles."""

import random
from datetime import UTC, datetime

from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.lab.scenarios.base import ScenarioContext
from app.lab.scenarios.catalog import SCENARIO_CATALOG
from app.lab.types import (
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticEventType,
)


def test_s05_network_timeout_with_underlying_success() -> None:
    """S05: Client times out, but underlying banking network settled payment."""
    s05 = SCENARIO_CATALOG["S05"]
    ctx = ScenarioContext(
        journey_id="jny_s05_test",
        order_id="ord_s05_test",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=Money.from_minor(1000_00, Currency.INR),
        currency=Currency.INR,
        payment_method=PaymentMethod.UPI,
        anchor_time=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        rng=random.Random(42),
        labels_version="1.0.0",
    )
    journey, events, gt = s05.generator_fn(ctx)

    # True economic outcome is CAPTURED
    assert journey.last_observed_state == "CAPTURED"
    assert gt.expected_final_payment_state == "CAPTURED"
    assert gt.recoverability == Recoverability.NOT_APPLICABLE
    assert gt.expected_recovery_strategy_class == RecoveryStrategyClass.NO_RECOVERY_NEEDED
    assert gt.expected_recovered_amount_cents == 1000_00

    # Event stream shows timeout event followed by reconciliation capture event
    event_types = [e.event_type for e in events]
    assert SyntheticEventType.PAYMENT_TIMED_OUT in event_types
    assert SyntheticEventType.PAYMENT_CAPTURED in event_types


def test_s17_late_asynchronous_success() -> None:
    """S17: Webhook notification arrives hours later due to queue delays."""
    s17 = SCENARIO_CATALOG["S17"]
    ctx = ScenarioContext(
        journey_id="jny_s17_test",
        order_id="ord_s17_test",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=Money.from_minor(1500_00, Currency.INR),
        currency=Currency.INR,
        payment_method=PaymentMethod.UPI,
        anchor_time=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        rng=random.Random(42),
        labels_version="1.0.0",
    )
    _journey, events, gt = s17.generator_fn(ctx)

    captured_event = next(e for e in events if e.event_type == SyntheticEventType.PAYMENT_CAPTURED)
    dt_occ = datetime.fromisoformat(captured_event.occurred_at)
    dt_emit = datetime.fromisoformat(captured_event.emitted_at)

    # Big delay in emission vs occurrence
    assert (dt_emit - dt_occ).total_seconds() >= 3600
    assert gt.recoverability == Recoverability.NOT_APPLICABLE
    assert gt.expected_recovery_strategy_class == RecoveryStrategyClass.NO_RECOVERY_NEEDED


def test_s18_out_of_order_event_delivery() -> None:
    """S18: PAYMENT_CAPTURED emitted before PAYMENT_AUTHORIZED."""
    s18 = SCENARIO_CATALOG["S18"]
    ctx = ScenarioContext(
        journey_id="jny_s18_test",
        order_id="ord_s18_test",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=Money.from_minor(2000_00, Currency.INR),
        currency=Currency.INR,
        payment_method=PaymentMethod.CARD,
        anchor_time=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        rng=random.Random(42),
        labels_version="1.0.0",
    )
    _journey, events, gt = s18.generator_fn(ctx)

    types = [e.event_type for e in events]
    idx_captured = types.index(SyntheticEventType.PAYMENT_CAPTURED)
    idx_authorized = types.index(SyntheticEventType.PAYMENT_AUTHORIZED)

    assert idx_captured < idx_authorized, (
        "Captured event should precede authorized event in emission stream"
    )
    assert gt.expected_final_payment_state == "CAPTURED"


def test_s19_duplicate_event_delivery() -> None:
    """S19: Exact duplicate of PAYMENT_FAILED event emitted into the stream."""
    s19 = SCENARIO_CATALOG["S19"]
    ctx = ScenarioContext(
        journey_id="jny_s19_test",
        order_id="ord_s19_test",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=Money.from_minor(500_00, Currency.INR),
        currency=Currency.INR,
        payment_method=PaymentMethod.CARD,
        anchor_time=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        rng=random.Random(42),
        labels_version="1.0.0",
    )
    _journey, events, _gt = s19.generator_fn(ctx)

    failed_events = [e for e in events if e.event_type == SyntheticEventType.PAYMENT_FAILED]
    assert len(failed_events) == 2
    # Duplicate repeats the same underlying event ID and payload
    assert failed_events[0].event_id == failed_events[1].event_id
    assert failed_events[0].payload == failed_events[1].payload
    # Second emission is later
    assert failed_events[1].emitted_at > failed_events[0].emitted_at


def test_s20_missing_intermediate_event() -> None:
    """S20: Intermediate authorization event is lost in network transport."""
    s20 = SCENARIO_CATALOG["S20"]
    ctx = ScenarioContext(
        journey_id="jny_s20_test",
        order_id="ord_s20_test",
        merchant_id="syn_mer_01",
        synthetic_customer_id="syn_cust_0001",
        amount=Money.from_minor(3000_00, Currency.INR),
        currency=Currency.INR,
        payment_method=PaymentMethod.CARD,
        anchor_time=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        rng=random.Random(42),
        labels_version="1.0.0",
    )
    _journey, events, gt = s20.generator_fn(ctx)

    types = [e.event_type for e in events]
    assert SyntheticEventType.PAYMENT_AUTHORIZED not in types
    assert SyntheticEventType.PAYMENT_CAPTURED in types
    assert gt.expected_final_payment_state == "CAPTURED"
