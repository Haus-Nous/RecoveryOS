"""RecoveryOS Synthetic Payment Laboratory.

A deterministic, reproducible payment laboratory generating realistic payment
journeys with explicit ground truth for downstream intelligence evaluation.
"""

from app.lab.generator import SyntheticLabGenerator
from app.lab.manifest import ManifestBuilder
from app.lab.models import (
    AttemptGroundTruth,
    GroundTruth,
    SyntheticLabConfig,
    SyntheticObservedEvent,
    SyntheticPaymentJourney,
)
from app.lab.scenarios.catalog import SCENARIO_CATALOG
from app.lab.types import (
    MerchantProfileType,
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticEventType,
    SyntheticFailureCategory,
)
from app.lab.validator import ValidationReport, validate_dataset

LAB_VERSION: str = "1.0.0"
SCHEMA_VERSION: str = "1.0.0"
SCENARIO_CATALOG_VERSION: str = "1.0.0"

__all__ = [
    "LAB_VERSION",
    "SCENARIO_CATALOG",
    "SCENARIO_CATALOG_VERSION",
    "SCHEMA_VERSION",
    "AttemptGroundTruth",
    "GroundTruth",
    "ManifestBuilder",
    "MerchantProfileType",
    "PaymentMethod",
    "Recoverability",
    "RecoveryStrategyClass",
    "SyntheticEventType",
    "SyntheticFailureCategory",
    "SyntheticLabConfig",
    "SyntheticLabGenerator",
    "SyntheticObservedEvent",
    "SyntheticPaymentJourney",
    "ValidationReport",
    "validate_dataset",
]
