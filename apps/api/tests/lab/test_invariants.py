"""Property and invariant testing across 50 pseudo-random seeds."""

from datetime import UTC, datetime

import pytest

from app.lab.generator import SyntheticLabGenerator
from app.lab.models import SyntheticLabConfig


@pytest.mark.parametrize("seed", list(range(1, 51)))
def test_50_seed_invariant_sweep(seed: int) -> None:
    """Rigorous 50-seed sweep verifying financial conservation, state machines, and isolation."""
    config = SyntheticLabConfig(
        seed=seed,
        journey_count=10,
        merchant_count=10,
        generation_profile="default",
    )
    generator = SyntheticLabGenerator(config)

    for journey, events, gt in generator.generate_stream():
        # 1. Financial Conservation
        assert journey.amount_in_cents > 0
        assert gt.expected_recovered_amount_cents >= 0
        assert gt.expected_recovered_amount_cents <= journey.amount_in_cents

        if gt.expected_final_payment_state == "CAPTURED":
            assert gt.expected_recovered_amount_cents == journey.amount_in_cents
            assert journey.last_observed_state == "CAPTURED"
        else:
            assert gt.expected_recovered_amount_cents == 0
            assert journey.last_observed_state == "FAILED"

        # 2. Strict Tenant Isolation
        m_id = journey.merchant_id
        assert m_id.startswith("syn_mer_")
        assert gt.merchant_id == m_id

        for evt in events:
            assert evt.merchant_id == m_id
            assert evt.journey_id == journey.journey_id
            assert evt.order_id == journey.order_id
            if evt.payment_id:
                assert evt.payment_id in journey.payment_ids

        # 3. Timezone Awareness
        dt_gen = datetime.fromisoformat(journey.generated_at)
        assert dt_gen.tzinfo is not None and dt_gen.tzinfo == UTC

        for evt in events:
            dt_occ = datetime.fromisoformat(evt.occurred_at)
            dt_emit = datetime.fromisoformat(evt.emitted_at)
            assert dt_occ.tzinfo == UTC
            assert dt_emit.tzinfo == UTC

        # 4. Multi-Attempt Consistency
        assert len(gt.attempt_truths) == len(journey.payment_ids)
        assert len(gt.attempt_truths) == gt.expected_number_of_attempts
