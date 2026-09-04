"""SQLAlchemy implementation of PaymentRepository."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ConcurrencyConflictError
from app.application.ports.repositories import PaymentRepository
from app.domain.entities.payment import Payment
from app.domain.types import MerchantId, OrderId, PaymentId
from app.infrastructure.persistence.mappers.payment_mapper import PaymentMapper
from app.infrastructure.persistence.models.payment import PaymentModel


class SqlAlchemyPaymentRepository(PaymentRepository):
    """PostgreSQL repository for Payment aggregates with tenant scoping and optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, merchant_id: MerchantId, payment_id: PaymentId) -> Payment | None:
        stmt = select(PaymentModel).where(
            PaymentModel.id == str(payment_id),
            PaymentModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return PaymentMapper.to_domain(model) if model is not None else None

    async def get_by_order_id(
        self, merchant_id: MerchantId, order_id: OrderId
    ) -> Sequence[Payment]:
        stmt = (
            select(PaymentModel)
            .where(
                PaymentModel.order_id == str(order_id),
                PaymentModel.merchant_id == str(merchant_id),
            )
            .order_by(PaymentModel.attempt_number.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [PaymentMapper.to_domain(m) for m in models]

    async def save(
        self,
        merchant_id: MerchantId,
        payment: Payment,
        expected_version: int | None = None,
    ) -> Payment:
        stmt = select(PaymentModel).where(
            PaymentModel.id == str(payment.id),
            PaymentModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = PaymentMapper.to_model(payment, version=1)
            self._session.add(new_model)
            await self._session.flush()
            return payment

        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyConflictError(
                entity_type="Payment",
                entity_id=str(payment.id),
                expected_version=expected_version,
                actual_version=existing.version,
            )

        new_version = existing.version + 1
        fail_cat = payment.failure.category.value if payment.failure else None
        fail_code = payment.failure.code if payment.failure else None
        fail_reason = payment.failure.reason if payment.failure else None
        fail_retryable = payment.failure.is_retryable_hint if payment.failure else None
        fail_at = payment.failure.occurred_at if payment.failure else None

        update_stmt = (
            update(PaymentModel)
            .where(
                PaymentModel.id == str(payment.id),
                PaymentModel.merchant_id == str(merchant_id),
                PaymentModel.version == existing.version,
            )
            .values(
                amount_minor=payment.amount.amount_minor,
                currency=payment.amount.currency.value,
                state=payment.state.value,
                attempt_number=payment.attempt_number,
                provider_reference=payment.provider_reference,
                failure_category=fail_cat,
                failure_code=fail_code,
                failure_reason=fail_reason,
                failure_is_retryable_hint=fail_retryable,
                failure_occurred_at=fail_at,
                updated_at=payment.updated_at,
                version=new_version,
            )
        )
        res = await self._session.execute(update_stmt)
        cursor_res = cast(CursorResult[Any], res)
        if cursor_res.rowcount == 0:
            raise ConcurrencyConflictError(
                entity_type="Payment",
                entity_id=str(payment.id),
                expected_version=existing.version,
            )

        await self._session.flush()
        return payment
