"""Tests verifying independent dataset validator and corruption detection."""

import argparse
import hashlib
import json
from pathlib import Path

from app.lab.cli import handle_generate
from app.lab.models import SyntheticLabConfig
from app.lab.validator import validate_dataset


def _generate_clean_dataset(out_dir: Path) -> Path:
    cfg = SyntheticLabConfig(
        seed=101,
        journey_count=20,
        merchant_count=5,
        generation_profile="default",
        output_dir=out_dir,
    )

    args = argparse.Namespace(
        seed=cfg.seed,
        journeys=cfg.journey_count,
        merchants=cfg.merchant_count,
        profile=cfg.generation_profile,
        output=cfg.output_dir,
        dry_run=False,
        persist=False,
        batch_size=100,
    )
    handle_generate(args)
    return out_dir / "ds_syn_default_s101_n20"


def test_clean_dataset_passes_validator(tmp_path: Path) -> None:
    """Valid dataset must pass validation with zero errors."""
    ds_dir = _generate_clean_dataset(tmp_path)
    report = validate_dataset(ds_dir)
    assert report.is_valid is True
    assert len(report.errors) == 0
    assert report.stats["journeys"] == 20


def test_validator_catches_file_checksum_corruption(tmp_path: Path) -> None:
    """Modifying a single byte of a file without updating manifest must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    target = ds_dir / "observed_events.jsonl"
    content = target.read_text()
    # Mutate one byte
    target.write_text(content + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Checksum mismatch for observed_events.jsonl" in err for err in report.errors)


def test_validator_catches_cross_tenant_violation(tmp_path: Path) -> None:
    """Events referencing a different merchant than the journey must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    target = ds_dir / "observed_events.jsonl"
    lines = target.read_text().splitlines()
    first_event = json.loads(lines[0])
    # Tamper merchant to a different tenant
    first_event["merchant_id"] = "syn_mer_99_tampered"
    lines[0] = json.dumps(first_event)
    target.write_text("\n".join(lines) + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Cross-tenant isolation violation" in err for err in report.errors)


def test_validator_catches_unknown_payment_id(tmp_path: Path) -> None:
    """Event referencing an unregistered payment ID must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    target = ds_dir / "observed_events.jsonl"
    lines = target.read_text().splitlines()
    first_event = json.loads(lines[0])
    first_event["payment_id"] = "unknown_payment_999"
    lines[0] = json.dumps(first_event)
    target.write_text("\n".join(lines) + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("references unknown payment_id" in err for err in report.errors)


def test_validator_catches_ground_truth_leakage_in_observed_data(tmp_path: Path) -> None:
    """Injecting a hidden ground truth label into observed journey must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    target = ds_dir / "journeys.jsonl"
    lines = target.read_text().splitlines()
    first_journey = json.loads(lines[0])
    first_journey["recoverability"] = "RECOVERABLE"  # Leaked!
    lines[0] = json.dumps(first_journey)
    target.write_text("\n".join(lines) + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Forbidden ground-truth keys leaked" in err for err in report.errors)


def test_validator_catches_negative_or_corrupted_money(tmp_path: Path) -> None:
    """Negative amount in journey must fail validation."""
    ds_dir = _generate_clean_dataset(tmp_path)
    target = ds_dir / "journeys.jsonl"
    lines = target.read_text().splitlines()
    first_journey = json.loads(lines[0])
    first_journey["amount_in_cents"] = -500  # Negative money!
    lines[0] = json.dumps(first_journey)
    target.write_text("\n".join(lines) + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Order amount must be positive integer" in err for err in report.errors)


def _update_manifest_summary_hash(ds_dir: Path) -> None:
    """Update manifest.json with the actual current SHA-256 and size of summary.json."""
    summary_path = ds_dir / "summary.json"
    manifest_path = ds_dir / "manifest.json"
    content = summary_path.read_bytes()
    new_hash = hashlib.sha256(content).hexdigest()
    new_size = len(content)

    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["file_hashes"]["summary.json"] = new_hash
    manifest_data["file_sizes_bytes"]["summary.json"] = new_size
    manifest_path.write_text(
        json.dumps(manifest_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def test_validator_catches_summary_scenario_count_corruption(tmp_path: Path) -> None:
    """Corrupting a scenario count in summary.json must fail even when manifest hash matches."""
    ds_dir = _generate_clean_dataset(tmp_path)
    summary_path = ds_dir / "summary.json"
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))

    # Corrupt a scenario count
    first_scenario = next(iter(summary_data["scenario_distribution"]))
    summary_data["scenario_distribution"][first_scenario]["count"] += 999
    summary_path.write_text(
        json.dumps(summary_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _update_manifest_summary_hash(ds_dir)

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any(
        f"Summary scenario count mismatch for {first_scenario}" in err for err in report.errors
    )


def test_validator_catches_summary_recoverability_count_corruption(tmp_path: Path) -> None:
    """Corrupting recoverability count in summary.json must fail even when manifest hash matches."""
    ds_dir = _generate_clean_dataset(tmp_path)
    summary_path = ds_dir / "summary.json"
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))

    # Corrupt recoverability count
    first_rec = next(iter(summary_data["recoverability_distribution"]))
    summary_data["recoverability_distribution"][first_rec]["count"] += 50
    summary_path.write_text(
        json.dumps(summary_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _update_manifest_summary_hash(ds_dir)

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any(
        f"Summary recoverability count mismatch for {first_rec}" in err for err in report.errors
    )


def test_validator_catches_summary_payment_method_count_corruption(tmp_path: Path) -> None:
    """Corrupting payment method count in summary.json must fail even when manifest hash matches."""
    ds_dir = _generate_clean_dataset(tmp_path)
    summary_path = ds_dir / "summary.json"
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))

    first_pm = next(iter(summary_data["payment_method_distribution"]))
    summary_data["payment_method_distribution"][first_pm]["count"] += 25
    summary_path.write_text(
        json.dumps(summary_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _update_manifest_summary_hash(ds_dir)

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any(
        f"Summary payment method count mismatch for {first_pm}" in err for err in report.errors
    )


def test_validator_catches_summary_event_count_corruption(tmp_path: Path) -> None:
    """Corrupting event count in summary.json must fail even when manifest hash matches."""
    ds_dir = _generate_clean_dataset(tmp_path)
    summary_path = ds_dir / "summary.json"
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))

    summary_data["total_events"] += 1234
    summary_path.write_text(
        json.dumps(summary_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    _update_manifest_summary_hash(ds_dir)

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Summary total_events mismatch" in err for err in report.errors)


def test_validator_catches_manifest_summary_disagreement(tmp_path: Path) -> None:
    """Disagreement between manifest actual_journey_count and summary total_journeys must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    manifest_path = ds_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest_data["actual_journey_count"] += 10
    manifest_path.write_text(
        json.dumps(manifest_data, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any("Manifest/summary journey count mismatch" in err for err in report.errors)


def test_validator_catches_scenario_catalog_inconsistency(tmp_path: Path) -> None:
    """Ground truth record whose recoverability contradicts the scenario catalog must fail."""
    ds_dir = _generate_clean_dataset(tmp_path)
    gt_path = ds_dir / "ground_truth.jsonl"
    lines = gt_path.read_text().splitlines()

    first_gt = json.loads(lines[0])
    s_id = first_gt["scenario_id"]
    # Tamper recoverability to contradict catalog
    first_gt["recoverability"] = (
        "NON_RECOVERABLE" if first_gt["recoverability"] != "NON_RECOVERABLE" else "RECOVERABLE"
    )
    lines[0] = json.dumps(first_gt)
    gt_path.write_text("\n".join(lines) + "\n")

    report = validate_dataset(ds_dir)
    assert report.is_valid is False
    assert any(f"Scenario {s_id} recoverability mismatch" in err for err in report.errors)
