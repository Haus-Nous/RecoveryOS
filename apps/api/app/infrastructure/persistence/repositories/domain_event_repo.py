"""SQLAlchemy implementation of DomainEventRepository."""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import DomainEventRepository
from app.domain.events.base import DomainEvent
from app.domain.types import MerchantId
from app.infrastructure.persistence.mappers.domain_event_mapper import DomainEventMapper
from app.infrastructure.persistence.models.domain_event import DomainEventModel


class SqlAlchemyDomainEventRepository(DomainEventRepository):
    """Append-only PostgreSQL repository for domain events."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, merchant_id: MerchantId | None, event: DomainEvent) -> None:
        model = DomainEventMapper.to_model(
            event,
            merchant_id=str(merchant_id) if merchant_id else None,
            recorded_at=datetime.now(UTC),
        )
        self._session.add(model)
        await self._session.flush()

    async def list_by_aggregate(
        self,
        merchant_id: MerchantId,
        aggregate_type: str,
        aggregate_id: str,
        limit: int = 100,
    ) -> Sequence[DomainEvent]:
        stmt = (
            select(DomainEventModel)
            .where(
                DomainEventModel.merchant_id == str(merchant_id),
                DomainEventModel.aggregate_type == aggregate_type,
                DomainEventModel.aggregate_id == aggregate_id,
            )
            .order_by(DomainEventModel.occurred_at.asc(), DomainEventModel.recorded_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [DomainEventMapper.to_domain(m) for m in models]
