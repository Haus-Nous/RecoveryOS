"""SQLAlchemy implementation of the UnitOfWork pattern."""

import uuid
from datetime import UTC, datetime
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.events.base import DomainEvent
from app.domain.types import MerchantId
from app.infrastructure.persistence.mappers.domain_event_mapper import unfreeze_payload
from app.infrastructure.persistence.models.outbox import OutboxMessageModel
from app.infrastructure.persistence.repositories.domain_event_repo import (
    SqlAlchemyDomainEventRepository,
)
from app.infrastructure.persistence.repositories.membership_repo import (
    SqlAlchemyMembershipRepository,
)
from app.infrastructure.persistence.repositories.order_repo import (
    SqlAlchemyOrderRepository,
)
from app.infrastructure.persistence.repositories.payment_repo import (
    SqlAlchemyPaymentRepository,
)
from app.infrastructure.persistence.repositories.policy_repo import (
    SqlAlchemyPolicyRepository,
)
from app.infrastructure.persistence.repositories.provider_connection_repo import (
    SqlAlchemyProviderConnectionRepository,
)
from app.infrastructure.persistence.repositories.recovery_action_repo import (
    SqlAlchemyRecoveryActionRepository,
)
from app.infrastructure.persistence.repositories.recovery_case_repo import (
    SqlAlchemyRecoveryCaseRepository,
)
from app.infrastructure.persistence.repositories.recovery_outcome_repo import (
    SqlAlchemyRecoveryOutcomeRepository,
)
from app.infrastructure.persistence.repositories.recovery_proposal_repo import (
    SqlAlchemyRecoveryProposalRepository,
)
from app.infrastructure.persistence.repositories.user_repo import (
    SqlAlchemyUserIdentityRepository,
    SqlAlchemyUserRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy Unit of Work managing transactional boundaries, outbox, and event logging."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._pending_events: list[tuple[MerchantId | None, DomainEvent]] = []

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self._pending_events.clear()

        # Instantiate tenant-scoped repositories bound to this transaction session
        self.orders = SqlAlchemyOrderRepository(self._session)
        self.payments = SqlAlchemyPaymentRepository(self._session)
        self.recovery_cases = SqlAlchemyRecoveryCaseRepository(self._session)
        self.recovery_proposals = SqlAlchemyRecoveryProposalRepository(self._session)
        self.policies = SqlAlchemyPolicyRepository(self._session)
        self.recovery_actions = SqlAlchemyRecoveryActionRepository(self._session)
        self.recovery_outcomes = SqlAlchemyRecoveryOutcomeRepository(self._session)
        self.events = SqlAlchemyDomainEventRepository(self._session)
        self.users = SqlAlchemyUserRepository(self._session)
        self.user_identities = SqlAlchemyUserIdentityRepository(self._session)
        self.memberships = SqlAlchemyMembershipRepository(self._session)
        self.payment_provider_connections = SqlAlchemyProviderConnectionRepository(self._session)

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session is not None:
            if exc_type is not None:
                await self.rollback()
            await self._session.close()
            self._session = None
            self._pending_events.clear()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("Cannot commit outside an active UnitOfWork session context.")

        # Persist all tracked domain events to domain_events log AND outbox_messages atomically
        for merchant_id, event in self._pending_events:
            # 1. Append-only event log
            await self.events.append(merchant_id, event)

            # 2. Transactional outbox entry
            outbox_entry = OutboxMessageModel(
                id=f"msg_{uuid.uuid4().hex}",
                event_id=str(event.event_id),
                merchant_id=str(merchant_id) if merchant_id else None,
                event_type=event.event_type,
                payload=unfreeze_payload(event.payload),
                occurred_at=event.occurred_at,
                created_at=datetime.now(UTC),
                published_at=None,
                attempt_count=0,
            )
            self._session.add(outbox_entry)

        await self._session.flush()
        await self._session.commit()
        self._pending_events.clear()

    async def rollback(self) -> None:
        if self._session is not None:
            await self._session.rollback()
            self._pending_events.clear()

    def track_event(self, merchant_id: MerchantId | None, event: DomainEvent) -> None:
        """Queue a domain event to be transactionally written on commit."""
        self._pending_events.append((merchant_id, event))
