"""SQLAlchemy implementation of RecoveryOutcomeRepository."""

from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import RecoveryOutcomeRepository
from app.domain.entities.recovery_outcome import RecoveryOutcome
from app.domain.types import MerchantId, RecoveryActionId, RecoveryCaseId
from app.infrastructure.persistence.mappers.recovery_outcome_mapper import RecoveryOutcomeMapper
from app.infrastructure.persistence.models.recovery_outcome import RecoveryOutcomeModel


class SqlAlchemyRecoveryOutcomeRepository(RecoveryOutcomeRepository):
    """PostgreSQL repository for recovery outcomes with verification state."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_action_id(
        self, merchant_id: MerchantId, action_id: RecoveryActionId
    ) -> RecoveryOutcome | None:
        stmt = select(RecoveryOutcomeModel).where(
            RecoveryOutcomeModel.recovery_action_id == str(action_id),
            RecoveryOutcomeModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return RecoveryOutcomeMapper.to_domain(model) if model is not None else None

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryOutcome]:
        stmt = (
            select(RecoveryOutcomeModel)
            .where(
                RecoveryOutcomeModel.recovery_case_id == str(case_id),
                RecoveryOutcomeModel.merchant_id == str(merchant_id),
            )
            .order_by(RecoveryOutcomeModel.observed_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [RecoveryOutcomeMapper.to_domain(m) for m in models]

    async def save(self, merchant_id: MerchantId, outcome: RecoveryOutcome) -> RecoveryOutcome:
        stmt = select(RecoveryOutcomeModel).where(
            RecoveryOutcomeModel.recovery_action_id == str(outcome.recovery_action_id),
            RecoveryOutcomeModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            new_model = RecoveryOutcomeMapper.to_model(outcome, merchant_id=str(merchant_id))
            self._session.add(new_model)
            await self._session.flush()
            return outcome

        update_stmt = (
            update(RecoveryOutcomeModel)
            .where(
                RecoveryOutcomeModel.recovery_action_id == str(outcome.recovery_action_id),
                RecoveryOutcomeModel.merchant_id == str(merchant_id),
            )
            .values(
                status=outcome.status.value,
                amount_recovered_minor=outcome.amount_recovered.amount_minor,
                currency=outcome.amount_recovered.currency.value,
                observed_at=outcome.observed_at,
                verification_status=outcome.verification_status.value,
                verification_reference=outcome.verification_reference,
                verified_at=outcome.verified_at,
            )
        )
        await self._session.execute(update_stmt)
        await self._session.flush()
        return outcome
