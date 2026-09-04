"""SQLAlchemy implementation of PolicyRepository."""

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ConcurrencyConflictError
from app.application.ports.repositories import PolicyRepository
from app.domain.entities.policy import Policy
from app.domain.types import MerchantId, PolicyId
from app.infrastructure.persistence.mappers.policy_mapper import PolicyMapper
from app.infrastructure.persistence.models.policy import PolicyModel


class SqlAlchemyPolicyRepository(PolicyRepository):
    """PostgreSQL repository for Policy aggregates with tenant scoping and optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_merchant_id(self, merchant_id: MerchantId) -> Policy | None:
        stmt = select(PolicyModel).where(PolicyModel.merchant_id == str(merchant_id))
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return PolicyMapper.to_domain(model) if model is not None else None

    async def get_by_id(self, merchant_id: MerchantId, policy_id: PolicyId) -> Policy | None:
        stmt = select(PolicyModel).where(
            PolicyModel.id == str(policy_id),
            PolicyModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return PolicyMapper.to_domain(model) if model is not None else None

    async def save(
        self,
        merchant_id: MerchantId,
        policy: Policy,
        expected_version: int | None = None,
    ) -> Policy:
        stmt = select(PolicyModel).where(
            PolicyModel.id == str(policy.id),
            PolicyModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = PolicyMapper.to_model(policy, version=1)
            self._session.add(new_model)
            await self._session.flush()
            return policy

        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyConflictError(
                entity_type="Policy",
                entity_id=str(policy.id),
                expected_version=expected_version,
                actual_version=existing.version,
            )

        new_version = existing.version + 1
        update_stmt = (
            update(PolicyModel)
            .where(
                PolicyModel.id == str(policy.id),
                PolicyModel.merchant_id == str(merchant_id),
                PolicyModel.version == existing.version,
            )
            .values(
                enabled=policy.enabled,
                max_retry_attempts=policy.max_retry_attempts,
                cooldown_seconds=policy.cooldown_seconds,
                auto_action_amount_limit_minor=policy.auto_action_amount_limit.amount_minor,
                review_required_above_minor=policy.review_required_above.amount_minor,
                currency=policy.auto_action_amount_limit.currency.value,
                allowed_strategies=[s.value for s in policy.allowed_strategies],
                updated_at=policy.updated_at,
                version=new_version,
            )
        )
        res = await self._session.execute(update_stmt)
        cursor_res = cast(CursorResult[Any], res)
        if cursor_res.rowcount == 0:
            raise ConcurrencyConflictError(
                entity_type="Policy",
                entity_id=str(policy.id),
                expected_version=existing.version,
            )

        await self._session.flush()
        return policy
