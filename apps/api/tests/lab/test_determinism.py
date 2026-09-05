"""Tests verifying deterministic reproduction of synthetic datasets across seeds."""

import argparse
import json
from pathlib import Path

from app.lab.cli import handle_generate
from app.lab.manifest import compute_file_sha256
from app.lab.models import SyntheticLabConfig


def test_identical_seed_produces_identical_dataset_hashes(tmp_path: Path) -> None:
    """CRITICAL: Same seed and configuration MUST produce bit-for-bit identical hashes."""
    dir1 = tmp_path / "run_1"
    dir2 = tmp_path / "run_2"

    cfg1 = SyntheticLabConfig(
        seed=1337,
        journey_count=50,
        merchant_count=10,
        generation_profile="default",
        output_dir=dir1,
    )
    cfg2 = SyntheticLabConfig(
        seed=1337,
        journey_count=50,
        merchant_count=10,
        generation_profile="default",
        output_dir=dir2,
    )

    args1 = argparse.Namespace(
        seed=cfg1.seed,
        journeys=cfg1.journey_count,
        merchants=cfg1.merchant_count,
        profile=cfg1.generation_profile,
        output=cfg1.output_dir,
        dry_run=False,
        persist=False,
        batch_size=100,
    )
    args2 = argparse.Namespace(
        seed=cfg2.seed,
        journeys=cfg2.journey_count,
        merchants=cfg2.merchant_count,
        profile=cfg2.generation_profile,
        output=cfg2.output_dir,
        dry_run=False,
        persist=False,
        batch_size=100,
    )
    assert handle_generate(args1) == 0
    assert handle_generate(args2) == 0

    ds1_dir = dir1 / "ds_syn_default_s1337_n50"
    ds2_dir = dir2 / "ds_syn_default_s1337_n50"

    manifest1 = json.loads((ds1_dir / "manifest.json").read_text())
    manifest2 = json.loads((ds2_dir / "manifest.json").read_text())

    # Manifest file_hashes must match exactly
    assert manifest1["file_hashes"] == manifest2["file_hashes"]
    assert manifest1["actual_journey_count"] == 50
    assert manifest2["actual_journey_count"] == 50

    # Physical on-disk files must have identical SHA-256 digests
    for filename in [
        "observed_events.jsonl",
        "journeys.jsonl",
        "ground_truth.jsonl",
        "summary.json",
    ]:
        h1 = compute_file_sha256(ds1_dir / filename)
        h2 = compute_file_sha256(ds2_dir / filename)
        assert h1 == h2, f"File {filename} produced divergent checksums across identical runs"
        assert h1 == manifest1["file_hashes"][filename]


def test_different_seeds_produce_distinct_datasets(tmp_path: Path) -> None:
    """Different seeds must produce different data and different checksums."""
    dir1 = tmp_path / "seed_42"
    dir2 = tmp_path / "seed_43"

    args1 = argparse.Namespace(
        seed=42,
        journeys=25,
        merchants=10,
        profile="default",
        output=dir1,
        dry_run=False,
        persist=False,
        batch_size=100,
    )
    args2 = argparse.Namespace(
        seed=43,
        journeys=25,
        merchants=10,
        profile="default",
        output=dir2,
        dry_run=False,
        persist=False,
        batch_size=100,
    )
    assert handle_generate(args1) == 0
    assert handle_generate(args2) == 0

    ds1_dir = dir1 / "ds_syn_default_s42_n25"
    ds2_dir = dir2 / "ds_syn_default_s43_n25"

    h1 = compute_file_sha256(ds1_dir / "journeys.jsonl")
    h2 = compute_file_sha256(ds2_dir / "journeys.jsonl")

    assert h1 != h2, "Different seeds unexpectedly produced identical journey datasets"
