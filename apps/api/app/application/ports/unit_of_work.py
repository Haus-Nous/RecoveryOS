"""Application Unit of Work protocol for transactional boundaries."""

from types import TracebackType
from typing import Protocol, Self

from app.application.ports.repositories import (
    DomainEventRepository,
    OrderRepository,
    PaymentRepository,
    PolicyRepository,
    RecoveryActionRepository,
    RecoveryCaseRepository,
    RecoveryOutcomeRepository,
    RecoveryProposalRepository,
)
from app.domain.events.base import DomainEvent
from app.domain.types import MerchantId


class UnitOfWork(Protocol):
    """Transactional boundary managing repository operations and atomic commits."""

    orders: OrderRepository
    payments: PaymentRepository
    recovery_cases: RecoveryCaseRepository
    recovery_proposals: RecoveryProposalRepository
    policies: PolicyRepository
    recovery_actions: RecoveryActionRepository
    recovery_outcomes: RecoveryOutcomeRepository
    events: DomainEventRepository

    async def __aenter__(self) -> Self:
        """Enter transactional context."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit transactional context (auto-rollback if uncommitted or on error)."""
        ...

    async def commit(self) -> None:
        """Commit the ongoing transaction atomically."""
        ...

    async def rollback(self) -> None:
        """Rollback the ongoing transaction."""
        ...

    def track_event(self, merchant_id: MerchantId | None, event: DomainEvent) -> None:
        """Queue a domain event to be written to domain_events and outbox_messages on commit."""
        ...
