"""Independent validator verifying synthetic dataset integrity, checksums, and safety."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.lab.scenarios.catalog import SCENARIO_CATALOG

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
    unique_merchants: set[str] = set()
    raw_payment_methods: dict[str, int] = {}
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
                m_id = j.get("merchant_id", "")
                journey_merchants[j_id] = m_id
                if m_id:
                    unique_merchants.add(m_id)
                pm = j.get("payment_method", "")
                if pm:
                    raw_payment_methods[pm] = raw_payment_methods.get(pm, 0) + 1
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
    raw_scenarios: dict[str, int] = {}
    raw_recoverability: dict[str, int] = {}
    raw_outcomes: dict[str, int] = {}
    raw_strategies: dict[str, int] = {}
    raw_failure_categories: dict[str, int] = {}

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

            # Track distributions from raw records
            s_id = gt.get("scenario_id", "")
            if s_id:
                raw_scenarios[s_id] = raw_scenarios.get(s_id, 0) + 1
            rec = gt.get("recoverability", "")
            if rec:
                raw_recoverability[rec] = raw_recoverability.get(rec, 0) + 1
            out = gt.get("expected_final_payment_state", "")
            if out:
                raw_outcomes[out] = raw_outcomes.get(out, 0) + 1
            strat = gt.get("expected_recovery_strategy_class", "")
            if strat:
                raw_strategies[strat] = raw_strategies.get(strat, 0) + 1
            fc = gt.get("failure_category", "")
            if fc:
                raw_failure_categories[fc] = raw_failure_categories.get(fc, 0) + 1

            # Scenario catalog consistency
            if not s_id or s_id not in SCENARIO_CATALOG:
                errors.append(f"Ground truth has unknown scenario_id '{s_id}' at line {line_num}")
            else:
                sc_def = SCENARIO_CATALOG[s_id]
                if fc != sc_def.failure_category.value:
                    errors.append(
                        f"Scenario {s_id} failure category mismatch: catalog has {sc_def.failure_category.value}, got {fc} at line {line_num}"
                    )
                if rec != sc_def.recoverability.value:
                    errors.append(
                        f"Scenario {s_id} recoverability mismatch: catalog has {sc_def.recoverability.value}, got {rec} at line {line_num}"
                    )
                if strat != sc_def.expected_strategy.value:
                    errors.append(
                        f"Scenario {s_id} strategy mismatch: catalog has {sc_def.expected_strategy.value}, got {strat} at line {line_num}"
                    )

            # Attempt truths validation
            att_truths = gt.get("attempt_truths", [])
            exp_attempts = gt.get("expected_number_of_attempts", 0)
            if not isinstance(att_truths, list) or len(att_truths) != exp_attempts:
                errors.append(
                    f"Ground truth attempt_truths count ({len(att_truths) if isinstance(att_truths, list) else 'invalid'}) "
                    f"!= expected_number_of_attempts ({exp_attempts}) at line {line_num}"
                )

    # 5. Distribution invariant checks
    if truth_count != journey_count:
        errors.append(
            f"Journey count ({journey_count}) does not match ground truth count ({truth_count})"
        )
    if sum(raw_scenarios.values()) != journey_count:
        errors.append(
            f"Scenario counts sum ({sum(raw_scenarios.values())}) != journey count ({journey_count})"
        )
    if sum(raw_recoverability.values()) != journey_count:
        errors.append(
            f"Recoverability counts sum ({sum(raw_recoverability.values())}) != journey count ({journey_count})"
        )
    if sum(raw_payment_methods.values()) != journey_count:
        errors.append(
            f"Payment method counts sum ({sum(raw_payment_methods.values())}) != journey count ({journey_count})"
        )
    if sum(raw_outcomes.values()) != journey_count:
        errors.append(
            f"Outcome counts sum ({sum(raw_outcomes.values())}) != journey count ({journey_count})"
        )

    # 6. Summary inspection & deep reconciliation
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Failed to parse summary.json: {e}")
        summary = {}

    if summary:
        if summary.get("total_journeys") != journey_count:
            errors.append(
                f"Summary total_journeys mismatch: summary has {summary.get('total_journeys')}, raw recomputed {journey_count}"
            )
        if "total_events" in summary and summary.get("total_events") != event_count:
            errors.append(
                f"Summary total_events mismatch: summary has {summary.get('total_events')}, raw recomputed {event_count}"
            )
        if "total_merchants" in summary and summary.get("total_merchants") != len(unique_merchants):
            errors.append(
                f"Summary total_merchants mismatch: summary has {summary.get('total_merchants')}, raw recomputed {len(unique_merchants)}"
            )

        # Scenario distribution reconciliation
        summary_scenarios = summary.get("scenario_distribution", {})
        for scen_key, s_info in summary_scenarios.items():
            exp_c = raw_scenarios.get(scen_key, 0)
            act_c = s_info.get("count") if isinstance(s_info, dict) else None
            if act_c != exp_c:
                errors.append(
                    f"Summary scenario count mismatch for {scen_key}: summary has {act_c}, raw recomputed {exp_c}"
                )
        for scen_key in raw_scenarios:
            if scen_key not in summary_scenarios:
                errors.append(f"Scenario {scen_key} in raw data missing from summary.json")

        # Recoverability distribution reconciliation
        summary_rec = summary.get("recoverability_distribution", {})
        for r_key, r_info in summary_rec.items():
            exp_c = raw_recoverability.get(r_key, 0)
            act_c = r_info.get("count") if isinstance(r_info, dict) else None
            if act_c != exp_c:
                errors.append(
                    f"Summary recoverability count mismatch for {r_key}: summary has {act_c}, raw recomputed {exp_c}"
                )
        for r_key in raw_recoverability:
            if r_key not in summary_rec:
                errors.append(f"Recoverability {r_key} in raw data missing from summary.json")

        # Payment method distribution reconciliation
        summary_pm = summary.get("payment_method_distribution", {})
        for pm_key, m_info in summary_pm.items():
            exp_c = raw_payment_methods.get(pm_key, 0)
            act_c = m_info.get("count") if isinstance(m_info, dict) else None
            if act_c != exp_c:
                errors.append(
                    f"Summary payment method count mismatch for {pm_key}: summary has {act_c}, raw recomputed {exp_c}"
                )
        for pm_key in raw_payment_methods:
            if pm_key not in summary_pm:
                errors.append(f"Payment method {pm_key} in raw data missing from summary.json")

        # Outcome distribution reconciliation
        summary_out = summary.get("outcome_distribution", {})
        for o_key, o_info in summary_out.items():
            exp_c = raw_outcomes.get(o_key, 0)
            act_c = o_info.get("count") if isinstance(o_info, dict) else None
            if act_c != exp_c:
                errors.append(
                    f"Summary outcome count mismatch for {o_key}: summary has {act_c}, raw recomputed {exp_c}"
                )
        for o_key in raw_outcomes:
            if o_key not in summary_out:
                errors.append(f"Outcome {o_key} in raw data missing from summary.json")

    # 7. Manifest count checks & manifest/summary agreement
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

    if summary:
        if manifest.get("actual_journey_count") != summary.get("total_journeys"):
            errors.append(
                f"Manifest/summary journey count mismatch: manifest says {manifest.get('actual_journey_count')}, summary says {summary.get('total_journeys')}"
            )
        if manifest_rec_counts.get("journeys") != summary.get("total_journeys"):
            errors.append(
                f"Manifest record_counts.journeys ({manifest_rec_counts.get('journeys')}) != summary total_journeys ({summary.get('total_journeys')})"
            )
        if "total_events" in summary and manifest_rec_counts.get("observed_events") != summary.get(
            "total_events"
        ):
            errors.append(
                f"Manifest record_counts.observed_events ({manifest_rec_counts.get('observed_events')}) != summary total_events ({summary.get('total_events')})"
            )
        if "total_merchants" in summary and manifest.get("merchant_count") != summary.get(
            "total_merchants"
        ):
            errors.append(
                f"Manifest merchant_count ({manifest.get('merchant_count')}) != summary total_merchants ({summary.get('total_merchants')})"
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
