"""Independent validator verifying synthetic dataset integrity, checksums, and safety."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FORBIDDEN_OBSERVED_KEYS = frozenset(
    {
        "recoverability",
        "root_cause",
        "expected_recovery_strategy_class",
        "expected_recovery_possible",
        "expected_eventual_recovery",
        "expected_final_payment_state",
        "expected_final_state",
        "scenario_id",
        "is_revenue_at_risk",
        "should_open_recovery_case",
        "attempt_truths",
        "duplicate_of_event_id",
        "transport_anomaly",
        "synthetic_duplicate",
        "expected_delivery_order",
    }
)

ALLOWED_JOURNEY_KEYS = frozenset(
    {
        "amount_in_cents",
        "currency",
        "generated_at",
        "journey_id",
        "last_observed_state",
        "merchant_id",
        "observed_event_ids",
        "order_id",
        "payment_ids",
        "payment_method",
        "synthetic_customer_id",
    }
)

ALLOWED_EVENT_ENVELOPE_KEYS = frozenset(
    {
        "emitted_at",
        "event_id",
        "event_type",
        "journey_id",
        "merchant_id",
        "occurred_at",
        "order_id",
        "payload",
        "payment_id",
        "sequence_number",
    }
)

ALLOWED_EVENT_PAYLOAD_KEYS = frozenset(
    {
        "amount_in_cents",
        "attempt_number",
        "currency",
        "error_code",
        "error_description",
        "instrument_ref",
        "order_id",
        "payment_id",
        "payment_method",
        "provider_reference",
        "status",
    }
)


@dataclass(slots=True)
class ValidationReport:
    """Report detailing validation findings and integrity status of a dataset."""

    is_valid: bool
    dataset_dir: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest for a file on disk."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_dataset(dataset_dir: Path) -> ValidationReport:
    """Perform comprehensive independent validation of a synthetic laboratory dataset."""
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, Any] = {}

    if not dataset_dir.is_dir():
        return ValidationReport(
            is_valid=False,
            dataset_dir=str(dataset_dir),
            errors=[f"Directory does not exist: {dataset_dir}"],
        )

    manifest_path = dataset_dir / "manifest.json"
    journeys_path = dataset_dir / "journeys.jsonl"
    events_path = dataset_dir / "observed_events.jsonl"
    truth_path = dataset_dir / "ground_truth.jsonl"
    summary_path = dataset_dir / "summary.json"

    required_files = [manifest_path, journeys_path, events_path, truth_path, summary_path]
    for rf in required_files:
        if not rf.exists():
            errors.append(f"Required artifact missing: {rf.name}")

    if errors:
        return ValidationReport(is_valid=False, dataset_dir=str(dataset_dir), errors=errors)

    # 1. Manifest verification
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return ValidationReport(
            is_valid=False,
            dataset_dir=str(dataset_dir),
            errors=[f"Failed to parse manifest.json: {e}"],
        )

    expected_hashes: dict[str, str] = manifest.get("file_hashes", {})
    for filename, exp_hash in expected_hashes.items():
        target_file = dataset_dir / filename
        if not target_file.exists():
            errors.append(f"Hashed file {filename} referenced in manifest does not exist")
            continue
        actual_hash = compute_file_sha256(target_file)
        if actual_hash != exp_hash:
            errors.append(
                f"Checksum mismatch for {filename}: expected {exp_hash}, got {actual_hash}"
            )

    # 2. Journeys inspection
    journey_ids: set[str] = set()
    journey_merchants: dict[str, str] = {}
    journey_orders: dict[str, str] = {}
    journey_amounts: dict[str, int] = {}
    journey_payments: dict[str, set[str]] = {}
    journey_event_ids: dict[str, set[str]] = {}
    journey_count = 0

    with journeys_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            journey_count += 1
            try:
                j = json.loads(line)
            except Exception as e:
                errors.append(f"Invalid JSON at journeys.jsonl line {line_num}: {e}")
                continue

            # Check allowed keys
            actual_keys = set(j.keys())
            unexpected = actual_keys - ALLOWED_JOURNEY_KEYS
            if unexpected:
                errors.append(f"Unexpected keys in journeys.jsonl line {line_num}: {unexpected}")

            # Check forbidden keys
            forbidden = actual_keys.intersection(FORBIDDEN_OBSERVED_KEYS)
            if forbidden:
                errors.append(
                    f"CRITICAL: Forbidden ground-truth keys leaked in journeys.jsonl line {line_num}: {forbidden}"
                )

            j_id = j.get("journey_id")
            if not j_id or j_id in journey_ids:
                errors.append(f"Duplicate or empty journey_id at journeys.jsonl line {line_num}")
            else:
                journey_ids.add(j_id)
                journey_merchants[j_id] = j.get("merchant_id", "")
                journey_orders[j_id] = j.get("order_id", "")
                journey_amounts[j_id] = j.get("amount_in_cents", 0)
                journey_payments[j_id] = set(j.get("payment_ids", []))
                journey_event_ids[j_id] = set(j.get("observed_event_ids", []))

            # Financial sanity
            amt = j.get("amount_in_cents", 0)
            if not isinstance(amt, int) or amt <= 0:
                errors.append(
                    f"Order amount must be positive integer minor units at journeys.jsonl line {line_num}"
                )

    # 3. Observed Events inspection
    event_count = 0
    with events_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            event_count += 1
            try:
                evt = json.loads(line)
            except Exception as e:
                errors.append(f"Invalid JSON at observed_events.jsonl line {line_num}: {e}")
                continue

            actual_keys = set(evt.keys())
            unexpected = actual_keys - ALLOWED_EVENT_ENVELOPE_KEYS
            if unexpected:
                errors.append(
                    f"Unexpected envelope keys in observed_events.jsonl line {line_num}: {unexpected}"
                )

            forbidden = actual_keys.intersection(FORBIDDEN_OBSERVED_KEYS)
            if forbidden:
                errors.append(
                    f"CRITICAL: Forbidden keys leaked in observed_events.jsonl line {line_num}: {forbidden}"
                )

            payload = evt.get("payload", {})
            if not isinstance(payload, dict):
                errors.append(f"Payload must be a dict at observed_events.jsonl line {line_num}")
            else:
                payload_keys = set(payload.keys())
                unexpected_payload = payload_keys - ALLOWED_EVENT_PAYLOAD_KEYS
                if unexpected_payload:
                    errors.append(
                        f"Unexpected payload keys in observed_events.jsonl line {line_num}: {unexpected_payload}"
                    )
                forbidden_payload = payload_keys.intersection(FORBIDDEN_OBSERVED_KEYS)
                if forbidden_payload:
                    errors.append(
                        f"CRITICAL: Forbidden keys leaked in payload at line {line_num}: {forbidden_payload}"
                    )

            # Tenant integrity check
            evt_j_id = evt.get("journey_id")
            if evt_j_id not in journey_ids:
                errors.append(
                    f"Observed event references unknown journey_id '{evt_j_id}' at line {line_num}"
                )
            else:
                if evt.get("merchant_id") != journey_merchants[evt_j_id]:
                    errors.append(
                        f"Cross-tenant isolation violation! Event merchant {evt.get('merchant_id')} "
                        f"does not match journey merchant {journey_merchants[evt_j_id]} at line {line_num}"
                    )
                if evt.get("order_id") != journey_orders[evt_j_id]:
                    errors.append(
                        f"Event order_id mismatch at line {line_num}: expected {journey_orders[evt_j_id]}"
                    )
                evt_p_id = evt.get("payment_id")
                if evt_p_id and evt_p_id not in journey_payments[evt_j_id]:
                    errors.append(
                        f"Event references unknown payment_id '{evt_p_id}' for journey '{evt_j_id}' at line {line_num}"
                    )

    # 4. Ground Truth inspection
    truth_count = 0
    with truth_path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            if not line.strip():
                continue
            truth_count += 1
            try:
                gt = json.loads(line)
            except Exception as e:
                errors.append(f"Invalid JSON at ground_truth.jsonl line {line_num}: {e}")
                continue

            gt_j_id = gt.get("journey_id")
            if gt_j_id not in journey_ids:
                errors.append(
                    f"Ground truth references unknown journey_id '{gt_j_id}' at line {line_num}"
                )
            else:
                # Check tenant match
                if gt.get("merchant_id") != journey_merchants[gt_j_id]:
                    errors.append(
                        f"Ground truth merchant {gt.get('merchant_id')} does not match journey merchant "
                        f"{journey_merchants[gt_j_id]} at line {line_num}"
                    )

                # Check financial conservation
                order_amt = journey_amounts[gt_j_id]
                rec_amt = gt.get("expected_recovered_amount_cents", 0)
                if not isinstance(rec_amt, int) or rec_amt < 0:
                    errors.append(
                        f"Recovered amount must be non-negative integer at ground_truth.jsonl line {line_num}"
                    )
                elif rec_amt > order_amt:
                    errors.append(
                        f"Financial conservation violation: recovered amount {rec_amt} > order amount {order_amt} "
                        f"at ground_truth.jsonl line {line_num}"
                    )

                eventual = gt.get("expected_eventual_recovery")
                if eventual is False and rec_amt != 0:
                    errors.append(
                        f"Non-recovered journey must have recovered amount = 0, got {rec_amt} at line {line_num}"
                    )

    # 5. Manifest count checks
    manifest_rec_counts = manifest.get("record_counts", {})
    if journey_count != manifest.get("actual_journey_count"):
        errors.append(
            f"Journey count mismatch: manifest says {manifest.get('actual_journey_count')}, counted {journey_count}"
        )
    if journey_count != manifest_rec_counts.get("journeys"):
        errors.append(
            f"Manifest journeys record count mismatch: {manifest_rec_counts.get('journeys')} vs {journey_count}"
        )
    if truth_count != manifest_rec_counts.get("ground_truth"):
        errors.append(
            f"Manifest ground_truth record count mismatch: {manifest_rec_counts.get('ground_truth')} vs {truth_count}"
        )
    if event_count != manifest_rec_counts.get("observed_events"):
        errors.append(
            f"Manifest observed_events count mismatch: {manifest_rec_counts.get('observed_events')} vs {event_count}"
        )

    stats["journeys"] = journey_count
    stats["events"] = event_count
    stats["ground_truth"] = truth_count
    stats["dataset_id"] = manifest.get("dataset_id", "")

    return ValidationReport(
        is_valid=len(errors) == 0,
        dataset_dir=str(dataset_dir),
        errors=errors,
        warnings=warnings,
        stats=stats,
    )
