"""Base definitions and interfaces for laboratory scenarios."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.lab.models import GroundTruth, SyntheticObservedEvent, SyntheticPaymentJourney
from app.lab.types import (
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticFailureCategory,
)

RECOVERABILITY_HORIZON_HOURS: int = 72


@dataclass(frozen=True, slots=True)
class ScenarioContext:
    """Contextual parameters supplied to a scenario generator function."""

    journey_id: str
    order_id: str
    merchant_id: str
    synthetic_customer_id: str
    amount: Money
    currency: Currency
    payment_method: PaymentMethod
    anchor_time: datetime
    rng: random.Random
    labels_version: str


class ScenarioGeneratorFn(Protocol):
    """Protocol for scenario generation functions."""

    def __call__(
        self, ctx: ScenarioContext
    ) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]: ...


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """Formal metadata definition and generator binding for a laboratory scenario."""

    scenario_id: str
    name: str
    description: str
    allowed_methods: frozenset[PaymentMethod]
    failure_category: SyntheticFailureCategory
    recoverability: Recoverability
    expected_strategy: RecoveryStrategyClass
    default_weight_bps: int
    is_transport_anomaly: bool
    generator_fn: Callable[
        [ScenarioContext],
        tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth],
    ]

    def validate_method_compatibility(self, method: PaymentMethod) -> None:
        """Ensure the chosen payment method is semantically valid for this scenario."""
        if method not in self.allowed_methods:
            raise ValueError(
                f"Payment method {method.value} is not supported by scenario {self.scenario_id}. "
                f"Allowed methods: {[m.value for m in self.allowed_methods]}"
            )
