"""Manifest generation and summary statistics builder for laboratory datasets."""

import hashlib
from pathlib import Path
from typing import Any

from app.lab.models import SyntheticLabConfig
from app.lab.serializer import to_canonical_json


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of an on-disk file."""
    hasher = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class ManifestBuilder:
    """Builds non-circular manifest and dataset summary with deterministic metadata."""

    def __init__(
        self,
        output_dir: Path,
        config: SyntheticLabConfig,
        lab_version: str = "1.0.0",
        schema_version: str = "1.0.0",
        scenario_catalog_version: str = "1.0.0",
    ) -> None:
        self.output_dir = output_dir
        self.config = config
        self.lab_version = lab_version
        self.schema_version = schema_version
        self.scenario_catalog_version = scenario_catalog_version

        # Accumulator for distributions
        self.scenarios: dict[str, int] = {}
        self.recoverability: dict[str, int] = {}
        self.methods: dict[str, int] = {}
        self.failure_categories: dict[str, int] = {}
        self.strategies: dict[str, int] = {}
        self.outcomes: dict[str, int] = {}
        self.attempts: dict[int, int] = {}
        self.total_events: int = 0
        self.merchants: set[str] = set()

    def record_journey_stats(
        self,
        scenario_id: str,
        recoverability: str,
        method: str,
        failure_category: str,
        strategy: str,
        outcome: str,
        num_attempts: int,
        num_events: int = 0,
        merchant_id: str = "",
    ) -> None:
        """Increment distribution counters for a generated journey."""
        self.scenarios[scenario_id] = self.scenarios.get(scenario_id, 0) + 1
        self.recoverability[recoverability] = self.recoverability.get(recoverability, 0) + 1
        self.methods[method] = self.methods.get(method, 0) + 1
        self.failure_categories[failure_category] = (
            self.failure_categories.get(failure_category, 0) + 1
        )
        self.strategies[strategy] = self.strategies.get(strategy, 0) + 1
        self.outcomes[outcome] = self.outcomes.get(outcome, 0) + 1
        self.attempts[num_attempts] = self.attempts.get(num_attempts, 0) + 1
        self.total_events += num_events
        if merchant_id:
            self.merchants.add(merchant_id)

    def write_summary(self) -> tuple[Path, str, int]:
        """Write summary.json and return its path, SHA-256 hash, and size in bytes."""
        total = sum(self.scenarios.values()) or 1

        summary_data: dict[str, Any] = {
            "attempts_distribution": {
                str(k): {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.attempts.items())
            },
            "failure_category_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.failure_categories.items())
            },
            "outcome_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.outcomes.items())
            },
            "payment_method_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.methods.items())
            },
            "recoverability_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.recoverability.items())
            },
            "scenario_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.scenarios.items())
            },
            "strategy_distribution": {
                k: {"count": v, "percentage": round(v / total * 100, 2)}
                for k, v in sorted(self.strategies.items())
            },
            "total_events": self.total_events,
            "total_journeys": total,
            "total_merchants": len(self.merchants),
        }

        summary_path = self.output_dir / "summary.json"
        content = to_canonical_json(summary_data) + "\n"
        b_content = content.encode("utf-8")
        with summary_path.open("wb") as f:
            f.write(b_content)

        summary_hash = hashlib.sha256(b_content).hexdigest()
        summary_size = len(b_content)
        return summary_path, summary_hash, summary_size

    def write_manifest(
        self,
        writer_stats: dict[str, Any],
        summary_hash: str,
        summary_size: int,
    ) -> Path:
        """Generate manifest.json with non-circular SHA-256 hashes of the 4 data files."""
        dataset_id = (
            f"ds_syn_{self.config.generation_profile}_s{self.config.seed}_"
            f"n{self.config.journey_count}"
        )

        manifest_data: dict[str, Any] = {
            "actual_journey_count": writer_stats["journeys"]["count"],
            "dataset_id": dataset_id,
            "file_hashes": {
                "ground_truth.jsonl": writer_stats["ground_truth"]["hash"],
                "journeys.jsonl": writer_stats["journeys"]["hash"],
                "observed_events.jsonl": writer_stats["events"]["hash"],
                "summary.json": summary_hash,
            },
            "file_sizes_bytes": {
                "ground_truth.jsonl": writer_stats["ground_truth"]["size_bytes"],
                "journeys.jsonl": writer_stats["journeys"]["size_bytes"],
                "observed_events.jsonl": writer_stats["events"]["size_bytes"],
                "summary.json": summary_size,
            },
            "generation_profile": self.config.generation_profile,
            "lab_version": self.lab_version,
            "merchant_count": self.config.merchant_count,
            "record_counts": {
                "ground_truth": writer_stats["ground_truth"]["count"],
                "journeys": writer_stats["journeys"]["count"],
                "observed_events": writer_stats["events"]["count"],
            },
            "requested_journey_count": self.config.journey_count,
            "scenario_catalog_version": self.scenario_catalog_version,
            "schema_version": self.schema_version,
            "seed": self.config.seed,
        }

        manifest_path = self.output_dir / "manifest.json"
        content = to_canonical_json(manifest_data) + "\n"
        with manifest_path.open("wb") as f:
            f.write(content.encode("utf-8"))

        return manifest_path
