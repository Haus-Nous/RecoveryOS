"""Bi-directional mapper for RecoveryCase domain aggregate and RecoveryCaseModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.types import MerchantId, PaymentId, RecoveryCaseId
from app.domain.values.currency import Currency
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.domain.values.money import Money
from app.infrastructure.persistence.models.recovery_case import RecoveryCaseModel


class RecoveryCaseMapper:
    """Explicit mapping between RecoveryCase domain aggregate and RecoveryCaseModel ORM entity."""

    @staticmethod
    def to_domain(model: RecoveryCaseModel) -> RecoveryCase:
        """Map ORM RecoveryCaseModel to pure RecoveryCase domain aggregate."""
        try:
            opened_at = model.opened_at
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=UTC)

            updated_at = model.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            currency = Currency.from_str(model.currency)
            money = Money.from_minor(model.amount_at_risk_minor, currency)
            state = RecoveryCaseState(model.state)

            failure: PaymentFailure | None = None
            if model.failure_category is not None:
                fail_time = model.failure_occurred_at or opened_at
                if fail_time.tzinfo is None:
                    fail_time = fail_time.replace(tzinfo=UTC)
                failure = PaymentFailure(
                    category=FailureCategory(model.failure_category),
                    code=model.failure_code,
                    reason=model.failure_reason or "Unknown failure context",
                    is_retryable_hint=bool(model.failure_is_retryable_hint),
                    occurred_at=fail_time,
                )

            return RecoveryCase(
                id=RecoveryCaseId(model.id),
                merchant_id=MerchantId(model.merchant_id),
                payment_id=PaymentId(model.payment_id),
                amount_at_risk=money,
                state=state,
                opened_at=opened_at,
                updated_at=updated_at,
                failure_context=failure,
                attempt_count=model.attempt_count,
                terminal_reason=model.terminal_reason,
            )
        except Exception as exc:
            raise DataCorruptionError("RecoveryCase", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: RecoveryCase, version: int = 1) -> RecoveryCaseModel:
        """Map pure RecoveryCase domain aggregate to ORM RecoveryCaseModel."""
        fail_cat = domain.failure_context.category.value if domain.failure_context else None
        fail_code = domain.failure_context.code if domain.failure_context else None
        fail_reason = domain.failure_context.reason if domain.failure_context else None
        fail_retryable = (
            domain.failure_context.is_retryable_hint if domain.failure_context else None
        )
        fail_at = domain.failure_context.occurred_at if domain.failure_context else None

        return RecoveryCaseModel(
            id=str(domain.id),
            merchant_id=str(domain.merchant_id),
            payment_id=str(domain.payment_id),
            amount_at_risk_minor=domain.amount_at_risk.amount_minor,
            currency=domain.amount_at_risk.currency.value,
            state=domain.state.value,
            opened_at=domain.opened_at,
            updated_at=domain.updated_at,
            attempt_count=domain.attempt_count,
            terminal_reason=domain.terminal_reason,
            failure_category=fail_cat,
            failure_code=fail_code,
            failure_reason=fail_reason,
            failure_is_retryable_hint=fail_retryable,
            failure_occurred_at=fail_at,
            version=version,
        )
