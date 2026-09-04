"""SQLAlchemy implementation of RecoveryProposalRepository."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import RecoveryProposalRepository
from app.domain.entities.recovery_proposal import RecoveryProposal
from app.domain.types import MerchantId, RecoveryCaseId, RecoveryProposalId
from app.infrastructure.persistence.mappers.recovery_proposal_mapper import RecoveryProposalMapper
from app.infrastructure.persistence.models.recovery_proposal import RecoveryProposalModel


class SqlAlchemyRecoveryProposalRepository(RecoveryProposalRepository):
    """PostgreSQL repository for diagnostic recovery proposals."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, merchant_id: MerchantId, proposal_id: RecoveryProposalId
    ) -> RecoveryProposal | None:
        stmt = select(RecoveryProposalModel).where(
            RecoveryProposalModel.id == str(proposal_id),
            RecoveryProposalModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return RecoveryProposalMapper.to_domain(model) if model is not None else None

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryProposal]:
        stmt = (
            select(RecoveryProposalModel)
            .where(
                RecoveryProposalModel.recovery_case_id == str(case_id),
                RecoveryProposalModel.merchant_id == str(merchant_id),
            )
            .order_by(RecoveryProposalModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [RecoveryProposalMapper.to_domain(m) for m in models]

    async def save(self, merchant_id: MerchantId, proposal: RecoveryProposal) -> RecoveryProposal:
        model = RecoveryProposalMapper.to_model(proposal, merchant_id=str(merchant_id))
        self._session.add(model)
        await self._session.flush()
        return proposal
