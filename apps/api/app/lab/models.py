"""Data structures and configuration models for the Synthetic Payment Laboratory."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.domain.types import ensure_utc_datetime
from app.lab.types import (
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticEventType,
    SyntheticFailureCategory,
)


@dataclass(frozen=True, slots=True)
class AttemptGroundTruth:
    """Hidden ground truth for an individual payment attempt within a journey."""

    payment_id: str
    attempt_number: int
    expected_final_state: str
    failure_category: SyntheticFailureCategory
    failure_code: str | None
    root_cause: str
    is_retryable: bool
    recoverability: Recoverability


@dataclass(frozen=True, slots=True)
class GroundTruth:
    """Hidden latent ground truth for evaluating downstream detection/recovery systems."""

    journey_id: str
    merchant_id: str
    scenario_id: str
    failure_category: SyntheticFailureCategory
    failure_code: str | None
    root_cause: str
    recoverability: Recoverability
    expected_recovery_strategy_class: RecoveryStrategyClass
    expected_recovery_possible: bool
    expected_eventual_recovery: bool
    expected_final_payment_state: str
    expected_number_of_attempts: int
    expected_recovered_amount_cents: int
    currency: str
    is_revenue_at_risk: bool
    should_open_recovery_case: bool
    synthetic_labels_version: str
    attempt_truths: list[AttemptGroundTruth] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SyntheticObservedEvent:
    """External provider-neutral event envelope as seen by an integration or webhook listener.

    CRITICAL: Strictly contains external data only. No ground truth or lab transport
    metadata is exposed here.
    """

    event_id: str
    journey_id: str
    merchant_id: str
    order_id: str
    payment_id: str | None
    event_type: SyntheticEventType
    occurred_at: str
    emitted_at: str
    sequence_number: int
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SyntheticPaymentJourney:
    """External representation of a payment journey as observed by downstream systems.

    CRITICAL: Contains zero hidden ground truth labels. `last_observed_state` is a neutral
    record of the final observed state in the stream.
    """

    journey_id: str
    merchant_id: str
    synthetic_customer_id: str
    order_id: str
    payment_ids: list[str]
    amount_in_cents: int
    currency: str
    payment_method: PaymentMethod
    last_observed_state: str
    observed_event_ids: list[str]
    generated_at: str


@dataclass(slots=True)
class SyntheticLabConfig:
    """Configuration options for deterministic synthetic payment laboratory generation."""

    seed: int = 42
    journey_count: int = 100
    merchant_count: int = 10
    generation_profile: str = "default"
    start_time: datetime = field(default_factory=lambda: datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC))
    currency_weights: dict[str, int] = field(default_factory=lambda: {"INR": 10000})
    method_weights: dict[PaymentMethod, int] = field(
        default_factory=lambda: {
            PaymentMethod.UPI: 5000,
            PaymentMethod.CARD: 3000,
            PaymentMethod.NETBANKING: 1000,
            PaymentMethod.WALLET: 600,
            PaymentMethod.EMI: 400,
        }
    )
    scenario_weights: dict[str, int] = field(default_factory=dict)
    output_dir: Path = field(default_factory=lambda: Path("artifacts/synthetic"))
    persist_to_database: bool = False
    batch_size: int = 500

    def __post_init__(self) -> None:
        self.start_time = ensure_utc_datetime(self.start_time)
        if self.journey_count < 1:
            raise ValueError(f"journey_count must be >= 1, got {self.journey_count}")
        if self.merchant_count < 1:
            raise ValueError(f"merchant_count must be >= 1, got {self.merchant_count}")
        if self.batch_size < 1:
            raise ValueError(f"batch_size must be >= 1, got {self.batch_size}")
        if not self.currency_weights or any(w < 0 for w in self.currency_weights.values()):
            raise ValueError("currency_weights must contain non-negative integer basis points")
        if not self.method_weights or any(w < 0 for w in self.method_weights.values()):
            raise ValueError("method_weights must contain non-negative integer basis points")
        if self.scenario_weights and any(w < 0 for w in self.scenario_weights.values()):
            raise ValueError("scenario_weights must contain non-negative integer basis points")
