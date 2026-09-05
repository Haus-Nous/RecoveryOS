"""Streaming deterministic generator for synthetic payment journeys and ground truth."""

import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta

from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.lab.models import (
    GroundTruth,
    SyntheticLabConfig,
    SyntheticObservedEvent,
    SyntheticPaymentJourney,
)
from app.lab.scenarios.base import ScenarioContext
from app.lab.scenarios.catalog import SCENARIO_CATALOG
from app.lab.types import (
    MerchantProfileType,
    PaymentMethod,
)


@dataclass(frozen=True, slots=True)
class SyntheticMerchant:
    """Synthetic tenant profile used during generation."""

    merchant_id: str
    name: str
    slug: str
    profile_type: MerchantProfileType


class SyntheticLabGenerator:
    """Deterministic generator producing observed journeys, events, and ground truth."""

    def __init__(self, config: SyntheticLabConfig, labels_version: str = "1.0.0") -> None:
        self.config = config
        self.labels_version = labels_version
        self._rng = random.Random(config.seed)
        self.merchants = self._generate_merchants(config.merchant_count)
        self._scenario_weights = self._build_scenario_weights()

    def _generate_merchants(self, count: int) -> list[SyntheticMerchant]:
        """Generate minimum 10 synthetic merchants deterministically across 5 profile archetypes."""
        profiles = [
            MerchantProfileType.LOW_RISK_RETAIL,
            MerchantProfileType.HIGH_VOLUME_MARKETPLACE,
            MerchantProfileType.SUBSCRIPTION_LIKE,
            MerchantProfileType.DIGITAL_SERVICES,
            MerchantProfileType.HIGH_TICKET_COMMERCE,
        ]
        merchants: list[SyntheticMerchant] = []
        for i in range(count):
            profile = profiles[i % len(profiles)]
            m_id = f"syn_mer_{i + 1:02d}"
            name = f"Synthetic {profile.value.replace('_', ' ').title()} {i + 1}"
            slug = f"syn-mer-{i + 1:02d}"
            merchants.append(
                SyntheticMerchant(
                    merchant_id=m_id,
                    name=name,
                    slug=slug,
                    profile_type=profile,
                )
            )
        return merchants

    def _build_scenario_weights(self) -> dict[str, int]:
        """Resolve scenario weights from config or catalog defaults (in bps)."""
        if self.config.scenario_weights:
            return dict(self.config.scenario_weights)
        return {s_id: sc.default_weight_bps for s_id, sc in SCENARIO_CATALOG.items()}

    def _choose_scenario_id(self) -> str:
        """Select a scenario deterministically according to basis-point weights."""
        scenario_ids = list(self._scenario_weights.keys())
        weights = [self._scenario_weights[s_id] for s_id in scenario_ids]
        return self._rng.choices(scenario_ids, weights=weights, k=1)[0]

    def _choose_method_for_scenario(
        self, allowed_methods: frozenset[PaymentMethod]
    ) -> PaymentMethod:
        """Pick a compatible payment method respecting configured method weights."""
        eligible_methods = [m for m in self.config.method_weights if m in allowed_methods]
        if not eligible_methods:
            eligible_methods = list(allowed_methods)
        weights = [self.config.method_weights.get(m, 100) for m in eligible_methods]
        return self._rng.choices(eligible_methods, weights=weights, k=1)[0]

    def _generate_amount_for_profile(
        self, profile: MerchantProfileType, currency: Currency
    ) -> Money:
        """Generate realistic integer minor-unit amount based on merchant archetype."""
        if profile == MerchantProfileType.LOW_RISK_RETAIL:
            # ₹200 to ₹3,500
            cents = self._rng.randint(200_00, 3500_00)
        elif profile == MerchantProfileType.HIGH_VOLUME_MARKETPLACE:
            # ₹150 to ₹1,800
            cents = self._rng.randint(150_00, 1800_00)
        elif profile == MerchantProfileType.SUBSCRIPTION_LIKE:
            # Fixed tier amounts: ₹499, ₹999, ₹1,499, ₹2,499, ₹4,999
            tiers = [499_00, 999_00, 1499_00, 2499_00, 4999_00]
            cents = self._rng.choice(tiers)
        elif profile == MerchantProfileType.DIGITAL_SERVICES:
            # ₹49 to ₹999
            cents = self._rng.randint(49_00, 999_00)
        elif profile == MerchantProfileType.HIGH_TICKET_COMMERCE:
            # ₹12,000 to ₹85,000
            cents = self._rng.randint(12000_00, 85000_00)
        else:
            cents = self._rng.randint(500_00, 5000_00)

        return Money.from_minor(cents, currency)

    def generate_journey(
        self, journey_index: int
    ) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
        """Generate a single deterministic payment journey with events and ground truth."""
        # Tenant selection: distribute journeys across merchants
        merchant = self.merchants[journey_index % len(self.merchants)]

        order_id = f"ord_syn_{self.config.seed}_{journey_index:06d}"
        journey_id = f"jny_syn_{self.config.seed}_{journey_index:06d}"
        cust_id = f"syn_cust_{(journey_index % 250) + 1:04d}"

        # Currency
        currency_keys = list(self.config.currency_weights.keys())
        currency_weights = [self.config.currency_weights[k] for k in currency_keys]
        curr_str = self._rng.choices(currency_keys, weights=currency_weights, k=1)[0]
        currency = Currency.from_str(curr_str)

        # Monetary amount
        amount = self._generate_amount_for_profile(merchant.profile_type, currency)

        # Scenario & method
        scenario_id = self._choose_scenario_id()
        scenario_def = SCENARIO_CATALOG[scenario_id]
        method = self._choose_method_for_scenario(scenario_def.allowed_methods)

        # Deterministic timestamp anchor for this journey
        journey_anchor = self.config.start_time + timedelta(seconds=journey_index * 15)

        ctx = ScenarioContext(
            journey_id=journey_id,
            order_id=order_id,
            merchant_id=merchant.merchant_id,
            synthetic_customer_id=cust_id,
            amount=amount,
            currency=currency,
            payment_method=method,
            anchor_time=journey_anchor,
            rng=self._rng,
            labels_version=self.labels_version,
        )

        return scenario_def.generator_fn(ctx)

    def generate_stream(
        self,
    ) -> Iterator[tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]]:
        """Streaming generator producing all requested journeys sequentially."""
        for idx in range(self.config.journey_count):
            yield self.generate_journey(idx)
