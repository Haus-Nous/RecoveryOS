"""Bi-directional mapper for Policy domain aggregate and PolicyModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.types import MerchantId, PolicyId
from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.infrastructure.persistence.models.policy import PolicyModel


class PolicyMapper:
    """Explicit mapping between Policy domain aggregate and PolicyModel ORM entity."""

    @staticmethod
    def to_domain(model: PolicyModel) -> Policy:
        """Map ORM PolicyModel to pure Policy domain aggregate."""
        try:
            created_at = model.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            updated_at = model.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            currency = Currency.from_str(model.currency)
            auto_limit = Money.from_minor(model.auto_action_amount_limit_minor, currency)
            review_limit = Money.from_minor(model.review_required_above_minor, currency)
            allowed = frozenset(RecoveryStrategy(s) for s in model.allowed_strategies)

            return Policy(
                id=PolicyId(model.id),
                merchant_id=MerchantId(model.merchant_id),
                enabled=model.enabled,
                max_retry_attempts=model.max_retry_attempts,
                cooldown_seconds=model.cooldown_seconds,
                auto_action_amount_limit=auto_limit,
                review_required_above=review_limit,
                allowed_strategies=allowed,
                created_at=created_at,
                updated_at=updated_at,
            )
        except Exception as exc:
            raise DataCorruptionError("Policy", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: Policy, version: int = 1) -> PolicyModel:
        """Map pure Policy domain aggregate to ORM PolicyModel."""
        return PolicyModel(
            id=str(domain.id),
            merchant_id=str(domain.merchant_id),
            enabled=domain.enabled,
            max_retry_attempts=domain.max_retry_attempts,
            cooldown_seconds=domain.cooldown_seconds,
            auto_action_amount_limit_minor=domain.auto_action_amount_limit.amount_minor,
            review_required_above_minor=domain.review_required_above.amount_minor,
            currency=domain.auto_action_amount_limit.currency.value,
            allowed_strategies=[s.value for s in domain.allowed_strategies],
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            version=version,
        )
