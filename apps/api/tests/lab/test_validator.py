"""Tests verifying independent dataset validator and corruption detection."""

import argparse
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
