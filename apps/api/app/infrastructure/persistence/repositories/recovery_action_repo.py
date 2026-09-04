"""SQLAlchemy implementation of RecoveryActionRepository."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ConcurrencyConflictError
from app.application.ports.repositories import RecoveryActionRepository
from app.domain.entities.recovery_action import RecoveryAction
from app.domain.types import MerchantId, RecoveryActionId, RecoveryCaseId
from app.infrastructure.persistence.mappers.recovery_action_mapper import RecoveryActionMapper
from app.infrastructure.persistence.models.recovery_action import RecoveryActionModel


class SqlAlchemyRecoveryActionRepository(RecoveryActionRepository):
    """PostgreSQL repository for RecoveryAction aggregates with tenant scoping."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, merchant_id: MerchantId, action_id: RecoveryActionId
    ) -> RecoveryAction | None:
        stmt = select(RecoveryActionModel).where(
            RecoveryActionModel.id == str(action_id),
            RecoveryActionModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return RecoveryActionMapper.to_domain(model) if model is not None else None

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryAction]:
        stmt = (
            select(RecoveryActionModel)
            .where(
                RecoveryActionModel.recovery_case_id == str(case_id),
                RecoveryActionModel.merchant_id == str(merchant_id),
            )
            .order_by(RecoveryActionModel.attempt_number.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [RecoveryActionMapper.to_domain(m) for m in models]

    async def save(
        self,
        merchant_id: MerchantId,
        action: RecoveryAction,
        expected_version: int | None = None,
    ) -> RecoveryAction:
        stmt = select(RecoveryActionModel).where(
            RecoveryActionModel.id == str(action.id),
            RecoveryActionModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = RecoveryActionMapper.to_model(
                action, merchant_id=str(merchant_id), version=1
            )
            self._session.add(new_model)
            await self._session.flush()
            return action

        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyConflictError(
                entity_type="RecoveryAction",
                entity_id=str(action.id),
                expected_version=expected_version,
                actual_version=existing.version,
            )

        new_version = existing.version + 1
        decision = action.authorization_decision.value if action.authorization_decision else None

        update_stmt = (
            update(RecoveryActionModel)
            .where(
                RecoveryActionModel.id == str(action.id),
                RecoveryActionModel.merchant_id == str(merchant_id),
                RecoveryActionModel.version == existing.version,
            )
            .values(
                strategy=action.strategy.value,
                state=action.state.value,
                authorization_decision=decision,
                authorization_reference=action.authorization_reference,
                attempt_number=action.attempt_number,
                failure_reason=action.failure_reason,
                updated_at=action.updated_at,
                version=new_version,
            )
        )
        res = await self._session.execute(update_stmt)
        cursor_res = cast(CursorResult[Any], res)
        if cursor_res.rowcount == 0:
            raise ConcurrencyConflictError(
                entity_type="RecoveryAction",
                entity_id=str(action.id),
                expected_version=existing.version,
            )

        await self._session.flush()
        return action
