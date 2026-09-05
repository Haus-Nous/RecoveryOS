"""Command-line interface for the RecoveryOS Synthetic Payment Laboratory."""

import argparse
import asyncio
import sys
import time
from pathlib import Path

from app.lab import LAB_VERSION, SCENARIO_CATALOG_VERSION, SCHEMA_VERSION
from app.lab.generator import SyntheticLabGenerator
from app.lab.manifest import ManifestBuilder
from app.lab.models import GroundTruth, SyntheticLabConfig, SyntheticPaymentJourney
from app.lab.scenarios.catalog import SCENARIO_CATALOG
from app.lab.serializer import StreamingDatasetWriter
from app.lab.validator import validate_dataset


def create_parser() -> argparse.ArgumentParser:
    """Build command line argument parser for synthetic lab operations."""
    parser = argparse.ArgumentParser(
        prog="python -m app.lab",
        description="RecoveryOS Synthetic Payment Laboratory CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate command
    gen_parser = subparsers.add_parser(
        "generate", help="Generate synthetic payment journeys, events, and ground truth"
    )
    gen_parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic pseudo-random generator seed (default: 42)",
    )
    gen_parser.add_argument(
        "--journeys",
        type=int,
        default=100,
        help="Number of journeys to generate (default: 100)",
    )
    gen_parser.add_argument(
        "--merchants",
        type=int,
        default=10,
        help="Number of synthetic merchants to generate (default: 10)",
    )
    gen_parser.add_argument(
        "--profile",
        type=str,
        default="default",
        help="Generation profile name (default: 'default')",
    )
    gen_parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/synthetic"),
        help="Output base directory for generated artifacts",
    )
    gen_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate planned distribution and counts without writing files or DB",
    )
    gen_parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist domain entities to test database (requires APP_ENV=test/local)",
    )
    gen_parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Batch size for writing / database persistence (default: 500)",
    )

    # validate command
    val_parser = subparsers.add_parser(
        "validate", help="Validate a generated synthetic dataset against integrity invariants"
    )
    val_parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Path to the synthetic dataset directory containing manifest.json",
    )

    return parser


def handle_generate(args: argparse.Namespace) -> int:
    """Execute the dataset generation workflow."""
    config = SyntheticLabConfig(
        seed=args.seed,
        journey_count=args.journeys,
        merchant_count=args.merchants,
        generation_profile=args.profile,
        output_dir=args.output,
        persist_to_database=args.persist,
        batch_size=args.batch_size,
    )

    dataset_id = f"ds_syn_{config.generation_profile}_s{config.seed}_n{config.journey_count}"
    target_dir = config.output_dir / dataset_id

    if args.dry_run:
        generator = SyntheticLabGenerator(config, labels_version=SCHEMA_VERSION)
        journey_count = 0
        event_count = 0
        for _journey, events, _gt in generator.generate_stream():
            journey_count += 1
            event_count += len(events)
        print(f"--- Synthetic Lab Dry Run: {dataset_id} ---")
        print(f"Seed: {config.seed}")
        print(f"Journeys: {journey_count}")
        print(f"Merchants: {config.merchant_count}")
        print(f"Generation Profile: {config.generation_profile}")
        print(f"Estimated Events: ~{event_count}")
        print(f"Available Scenarios: {len(SCENARIO_CATALOG)}")
        print(f"Target Directory: {target_dir}")
        print("Dry run completed successfully. No files or database records written.")
        return 0

    print(f"Generating synthetic payment dataset '{dataset_id}'...")
    start_time = time.perf_counter()

    generator = SyntheticLabGenerator(config, labels_version=SCHEMA_VERSION)
    writer = StreamingDatasetWriter(target_dir)
    manifest_builder = ManifestBuilder(
        target_dir,
        config,
        lab_version=LAB_VERSION,
        schema_version=SCHEMA_VERSION,
        scenario_catalog_version=SCENARIO_CATALOG_VERSION,
    )

    # Streaming production
    persist_buffer: list[tuple[SyntheticPaymentJourney, GroundTruth]] = []
    for journey, events, gt in generator.generate_stream():
        writer.write_journey(journey, events, gt)
        manifest_builder.record_journey_stats(
            scenario_id=gt.scenario_id,
            recoverability=gt.recoverability.value,
            method=journey.payment_method.value,
            failure_category=gt.failure_category.value,
            strategy=gt.expected_recovery_strategy_class.value,
            outcome=gt.expected_final_payment_state,
            num_attempts=gt.expected_number_of_attempts,
            num_events=len(events),
            merchant_id=journey.merchant_id,
        )
        if args.persist:
            persist_buffer.append((journey, gt))

    writer_stats = writer.close()
    summary_path, summary_hash, summary_size = manifest_builder.write_summary()
    manifest_path = manifest_builder.write_manifest(writer_stats, summary_hash, summary_size)

    elapsed = time.perf_counter() - start_time
    print(f"Generation completed in {elapsed:.3f}s")
    print(f"Dataset directory: {target_dir}")
    print(f"Journeys: {writer_stats['journeys']['count']}")
    print(f"Events: {writer_stats['events']['count']}")
    print(f"Summary written: {summary_path.name}")
    print(f"Manifest written: {manifest_path.name}")

    # Optional database persistence
    if args.persist:
        print("Persisting synthetic entities to test database...")
        from app.infrastructure.database import get_session_factory
        from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
        from app.lab.persistence import persist_synthetic_batch, seed_synthetic_merchants

        async def _run_persistence() -> None:
            session_factory = get_session_factory()
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                await seed_synthetic_merchants(uow, generator.merchants)
                await persist_synthetic_batch(uow, persist_buffer)
                await uow.commit()

        asyncio.run(_run_persistence())
        print(f"Persisted {len(persist_buffer)} journeys to database.")

    return 0


def handle_validate(args: argparse.Namespace) -> int:
    """Execute the dataset validation workflow."""
    print(f"Validating dataset at: {args.dataset_dir}")
    report = validate_dataset(args.dataset_dir)
    if report.is_valid:
        print("SUCCESS: Dataset is valid and passes all integrity invariants.")
        print(f"Journeys: {report.stats.get('journeys')}")
        print(f"Events: {report.stats.get('events')}")
        print(f"Ground truth records: {report.stats.get('ground_truth')}")
        return 0
    else:
        print("FAILURE: Dataset validation errors encountered:", file=sys.stderr)
        for err in report.errors:
            print(f" - {err}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command == "generate":
        return handle_generate(args)
    elif args.command == "validate":
        return handle_validate(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
