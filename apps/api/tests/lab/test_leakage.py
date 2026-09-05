"""Tests verifying zero ground truth or transport leakage in observed datasets."""

import argparse
import json
from pathlib import Path

from app.lab.cli import handle_generate
from app.lab.models import SyntheticLabConfig
from app.lab.validator import (
    ALLOWED_EVENT_ENVELOPE_KEYS,
    ALLOWED_EVENT_PAYLOAD_KEYS,
    ALLOWED_JOURNEY_KEYS,
    FORBIDDEN_OBSERVED_KEYS,
)


def test_dual_layer_leakage_protection(tmp_path: Path) -> None:
    """CRITICAL: Observed files must never leak hidden ground truth or transport lab labels."""
    cfg = SyntheticLabConfig(
        seed=999,
        journey_count=50,
        merchant_count=10,
        generation_profile="default",
        output_dir=tmp_path,
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
    assert handle_generate(args) == 0
    ds_dir = tmp_path / "ds_syn_default_s999_n50"

    journeys_file = ds_dir / "journeys.jsonl"
    events_file = ds_dir / "observed_events.jsonl"

    # 1. Raw string inspection for forbidden tokens
    for token in FORBIDDEN_OBSERVED_KEYS:
        token_bytes = f'"{token}"'.encode()
        assert token_bytes not in journeys_file.read_bytes(), f"Leaked {token} in journeys.jsonl"
        assert token_bytes not in events_file.read_bytes(), (
            f"Leaked {token} in observed_events.jsonl"
        )

    # 2. Strict Allowed Schema validation for Journeys
    with journeys_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            j = json.loads(line)
            actual_keys = set(j.keys())
            unexpected = actual_keys - ALLOWED_JOURNEY_KEYS
            assert not unexpected, f"Unexpected keys in journeys.jsonl: {unexpected}"

    # 3. Strict Allowed Schema validation for Observed Events
    with events_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            evt = json.loads(line)
            actual_envelope = set(evt.keys())
            unexpected_envelope = actual_envelope - ALLOWED_EVENT_ENVELOPE_KEYS
            assert not unexpected_envelope, (
                f"Unexpected envelope keys in observed_events.jsonl: {unexpected_envelope}"
            )

            payload = evt["payload"]
            actual_payload = set(payload.keys())
            unexpected_payload = actual_payload - ALLOWED_EVENT_PAYLOAD_KEYS
            assert not unexpected_payload, (
                f"Unexpected payload keys in observed_events.jsonl: {unexpected_payload}"
            )
