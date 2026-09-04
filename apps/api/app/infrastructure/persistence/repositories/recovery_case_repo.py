"""SQLAlchemy implementation of RecoveryCaseRepository."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ConcurrencyConflictError
from app.application.ports.repositories import RecoveryCaseRepository
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.types import MerchantId, PaymentId, RecoveryCaseId
from app.infrastructure.persistence.mappers.recovery_case_mapper import RecoveryCaseMapper
from app.infrastructure.persistence.models.recovery_case import RecoveryCaseModel


class SqlAlchemyRecoveryCaseRepository(RecoveryCaseRepository):
    """PostgreSQL repository for RecoveryCase aggregates with tenant scoping."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> RecoveryCase | None:
        stmt = select(RecoveryCaseModel).where(
            RecoveryCaseModel.id == str(case_id),
            RecoveryCaseModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return RecoveryCaseMapper.to_domain(model) if model is not None else None

    async def get_by_payment_id(
        self, merchant_id: MerchantId, payment_id: PaymentId
    ) -> RecoveryCase | None:
        stmt = select(RecoveryCaseModel).where(
            RecoveryCaseModel.payment_id == str(payment_id),
            RecoveryCaseModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return RecoveryCaseMapper.to_domain(model) if model is not None else None

    async def list_by_state(
        self,
        merchant_id: MerchantId,
        state: RecoveryCaseState,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RecoveryCase]:
        stmt = (
            select(RecoveryCaseModel)
            .where(
                RecoveryCaseModel.merchant_id == str(merchant_id),
                RecoveryCaseModel.state == state.value,
            )
            .order_by(RecoveryCaseModel.opened_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [RecoveryCaseMapper.to_domain(m) for m in models]

    async def save(
        self,
        merchant_id: MerchantId,
        case: RecoveryCase,
        expected_version: int | None = None,
    ) -> RecoveryCase:
        stmt = select(RecoveryCaseModel).where(
            RecoveryCaseModel.id == str(case.id),
            RecoveryCaseModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = RecoveryCaseMapper.to_model(case, version=1)
            self._session.add(new_model)
            await self._session.flush()
            return case

        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyConflictError(
                entity_type="RecoveryCase",
                entity_id=str(case.id),
                expected_version=expected_version,
                actual_version=existing.version,
            )

        new_version = existing.version + 1
        fail_cat = case.failure_context.category.value if case.failure_context else None
        fail_code = case.failure_context.code if case.failure_context else None
        fail_reason = case.failure_context.reason if case.failure_context else None
        fail_retryable = case.failure_context.is_retryable_hint if case.failure_context else None
        fail_at = case.failure_context.occurred_at if case.failure_context else None

        update_stmt = (
            update(RecoveryCaseModel)
            .where(
                RecoveryCaseModel.id == str(case.id),
                RecoveryCaseModel.merchant_id == str(merchant_id),
                RecoveryCaseModel.version == existing.version,
            )
            .values(
                amount_at_risk_minor=case.amount_at_risk.amount_minor,
                currency=case.amount_at_risk.currency.value,
                state=case.state.value,
                attempt_count=case.attempt_count,
                terminal_reason=case.terminal_reason,
                failure_category=fail_cat,
                failure_code=fail_code,
                failure_reason=fail_reason,
                failure_is_retryable_hint=fail_retryable,
                failure_occurred_at=fail_at,
                updated_at=case.updated_at,
                version=new_version,
            )
        )
        res = await self._session.execute(update_stmt)
        cursor_res = cast(CursorResult[Any], res)
        if cursor_res.rowcount == 0:
            raise ConcurrencyConflictError(
                entity_type="RecoveryCase",
                entity_id=str(case.id),
                expected_version=existing.version,
            )

        await self._session.flush()
        return case
