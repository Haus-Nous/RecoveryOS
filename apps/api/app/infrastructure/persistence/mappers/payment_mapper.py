"""Bi-directional mapper for Payment domain aggregate and PaymentModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.payment import Payment, PaymentState
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.currency import Currency
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.domain.values.money import Money
from app.infrastructure.persistence.models.payment import PaymentModel


class PaymentMapper:
    """Explicit mapping between Payment domain aggregate and PaymentModel ORM entity."""

    @staticmethod
    def to_domain(model: PaymentModel) -> Payment:
        """Map ORM PaymentModel to pure Payment domain aggregate."""
        try:
            created_at = model.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            updated_at = model.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            currency = Currency.from_str(model.currency)
            money = Money.from_minor(model.amount_minor, currency)
            state = PaymentState(model.state)

            failure: PaymentFailure | None = None
            if model.failure_category is not None:
                fail_time = model.failure_occurred_at or updated_at
                if fail_time.tzinfo is None:
                    fail_time = fail_time.replace(tzinfo=UTC)
                failure = PaymentFailure(
                    category=FailureCategory(model.failure_category),
                    code=model.failure_code,
                    reason=model.failure_reason or "Unknown payment failure reason",
                    is_retryable_hint=bool(model.failure_is_retryable_hint),
                    occurred_at=fail_time,
                )

            return Payment(
                id=PaymentId(model.id),
                merchant_id=MerchantId(model.merchant_id),
                order_id=OrderId(model.order_id),
                amount=money,
                state=state,
                attempt_number=model.attempt_number,
                created_at=created_at,
                updated_at=updated_at,
                failure=failure,
                provider_reference=model.provider_reference,
            )
        except Exception as exc:
            raise DataCorruptionError("Payment", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: Payment, version: int = 1) -> PaymentModel:
        """Map pure Payment domain aggregate to ORM PaymentModel."""
        fail_cat = domain.failure.category.value if domain.failure else None
        fail_code = domain.failure.code if domain.failure else None
        fail_reason = domain.failure.reason if domain.failure else None
        fail_retryable = domain.failure.is_retryable_hint if domain.failure else None
        fail_at = domain.failure.occurred_at if domain.failure else None

        return PaymentModel(
            id=str(domain.id),
            merchant_id=str(domain.merchant_id),
            order_id=str(domain.order_id),
            amount_minor=domain.amount.amount_minor,
            currency=domain.amount.currency.value,
            state=domain.state.value,
            attempt_number=domain.attempt_number,
            provider_reference=domain.provider_reference,
            failure_category=fail_cat,
            failure_code=fail_code,
            failure_reason=fail_reason,
            failure_is_retryable_hint=fail_retryable,
            failure_occurred_at=fail_at,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            version=version,
        )
