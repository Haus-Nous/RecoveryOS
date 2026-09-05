"""Deterministic JSON serialization and streaming file writer with inline SHA-256 calculation."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.lab.models import (
    AttemptGroundTruth,
    GroundTruth,
    SyntheticObservedEvent,
    SyntheticPaymentJourney,
)


def to_canonical_json(data: dict[str, Any]) -> str:
    """Serialize data to a canonical, reproducible JSON string with sorted keys."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def serialize_observed_event(event: SyntheticObservedEvent) -> dict[str, Any]:
    """Serialize an external observed event envelope.

    STRICT: Contains only external provider-neutral attributes.
    """
    return {
        "emitted_at": event.emitted_at,
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "journey_id": event.journey_id,
        "merchant_id": event.merchant_id,
        "occurred_at": event.occurred_at,
        "order_id": event.order_id,
        "payload": event.payload,
        "payment_id": event.payment_id,
        "sequence_number": event.sequence_number,
    }


def serialize_payment_journey(journey: SyntheticPaymentJourney) -> dict[str, Any]:
    """Serialize an external observed journey summary.

    STRICT: Contains zero hidden ground-truth labels.
    """
    return {
        "amount_in_cents": journey.amount_in_cents,
        "currency": journey.currency,
        "generated_at": journey.generated_at,
        "journey_id": journey.journey_id,
        "last_observed_state": journey.last_observed_state,
        "merchant_id": journey.merchant_id,
        "observed_event_ids": journey.observed_event_ids,
        "order_id": journey.order_id,
        "payment_ids": journey.payment_ids,
        "payment_method": journey.payment_method.value,
        "synthetic_customer_id": journey.synthetic_customer_id,
    }


def serialize_attempt_ground_truth(att: AttemptGroundTruth) -> dict[str, Any]:
    """Serialize ground truth for an individual payment attempt."""
    return {
        "attempt_number": att.attempt_number,
        "expected_final_state": att.expected_final_state,
        "failure_category": att.failure_category.value,
        "failure_code": att.failure_code,
        "is_retryable": att.is_retryable,
        "payment_id": att.payment_id,
        "recoverability": att.recoverability.value,
        "root_cause": att.root_cause,
    }


def serialize_ground_truth(gt: GroundTruth) -> dict[str, Any]:
    """Serialize latent evaluation ground truth."""
    return {
        "attempt_truths": [serialize_attempt_ground_truth(a) for a in gt.attempt_truths],
        "currency": gt.currency,
        "expected_eventual_recovery": gt.expected_eventual_recovery,
        "expected_final_payment_state": gt.expected_final_payment_state,
        "expected_number_of_attempts": gt.expected_number_of_attempts,
        "expected_recovered_amount_cents": gt.expected_recovered_amount_cents,
        "expected_recovery_possible": gt.expected_recovery_possible,
        "expected_recovery_strategy_class": gt.expected_recovery_strategy_class.value,
        "failure_category": gt.failure_category.value,
        "failure_code": gt.failure_code,
        "is_revenue_at_risk": gt.is_revenue_at_risk,
        "journey_id": gt.journey_id,
        "merchant_id": gt.merchant_id,
        "recoverability": gt.recoverability.value,
        "root_cause": gt.root_cause,
        "scenario_id": gt.scenario_id,
        "should_open_recovery_case": gt.should_open_recovery_case,
        "synthetic_labels_version": gt.synthetic_labels_version,
    }


class StreamingDatasetWriter:
    """Manages streaming writes to JSONL files while computing SHA-256 hashes on the fly."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.events_path = output_dir / "observed_events.jsonl"
        self.journeys_path = output_dir / "journeys.jsonl"
        self.truth_path = output_dir / "ground_truth.jsonl"

        self.events_hasher = hashlib.sha256()
        self.journeys_hasher = hashlib.sha256()
        self.truth_hasher = hashlib.sha256()

        self.events_file = self.events_path.open("w", encoding="utf-8")
        self.journeys_file = self.journeys_path.open("w", encoding="utf-8")
        self.truth_file = self.truth_path.open("w", encoding="utf-8")

        self.event_count = 0
        self.journey_count = 0

    def write_journey(
        self,
        journey: SyntheticPaymentJourney,
        events: list[SyntheticObservedEvent],
        ground_truth: GroundTruth,
    ) -> None:
        """Write a single journey, its observed events, and its ground truth."""
        # Write journey
        j_dict = serialize_payment_journey(journey)
        j_line = to_canonical_json(j_dict) + "\n"
        b_j = j_line.encode("utf-8")
        self.journeys_file.write(j_line)
        self.journeys_hasher.update(b_j)
        self.journey_count += 1

        # Write events
        for evt in events:
            e_dict = serialize_observed_event(evt)
            e_line = to_canonical_json(e_dict) + "\n"
            b_e = e_line.encode("utf-8")
            self.events_file.write(e_line)
            self.events_hasher.update(b_e)
            self.event_count += 1

        # Write ground truth
        gt_dict = serialize_ground_truth(ground_truth)
        gt_line = to_canonical_json(gt_dict) + "\n"
        b_gt = gt_line.encode("utf-8")
        self.truth_file.write(gt_line)
        self.truth_hasher.update(b_gt)

    def close(self) -> dict[str, Any]:
        """Close open file handles and return file hashes, sizes, and record counts."""
        self.events_file.close()
        self.journeys_file.close()
        self.truth_file.close()

        return {
            "events": {
                "hash": self.events_hasher.hexdigest(),
                "size_bytes": self.events_path.stat().st_size,
                "count": self.event_count,
            },
            "journeys": {
                "hash": self.journeys_hasher.hexdigest(),
                "size_bytes": self.journeys_path.stat().st_size,
                "count": self.journey_count,
            },
            "ground_truth": {
                "hash": self.truth_hasher.hexdigest(),
                "size_bytes": self.truth_path.stat().st_size,
                "count": self.journey_count,
            },
        }
