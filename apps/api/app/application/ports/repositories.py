"""Application repository interfaces (ports) for financial domain aggregates.

CRITICAL INVARIANTS:
1. Every method MUST operate on and return pure Domain Entities, never ORM models.
2. Every aggregate query/mutation is explicitly scoped by MerchantId to ensure tenant isolation.
3. Repositories MUST NEVER auto-commit; commit/rollback is the sole domain of the Unit of Work.
"""

from collections.abc import Sequence
from typing import Protocol

from app.domain.entities.order import Order
from app.domain.entities.payment import Payment
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_action import RecoveryAction
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.entities.recovery_outcome import RecoveryOutcome
from app.domain.entities.recovery_proposal import RecoveryProposal
from app.domain.events.base import DomainEvent
from app.domain.types import (
    MerchantId,
    OrderId,
    PaymentId,
    PolicyId,
    RecoveryActionId,
    RecoveryCaseId,
    RecoveryProposalId,
)


class OrderRepository(Protocol):
    """Repository port for Order aggregates."""

    async def get_by_id(self, merchant_id: MerchantId, order_id: OrderId) -> Order | None:
        """Fetch order by ID scoped by merchant. Returns None if not found."""
        ...

    async def save(
        self, merchant_id: MerchantId, order: Order, expected_version: int | None = None
    ) -> Order:
        """Persist a new order or update an existing order with optimistic concurrency check.

        Raises:
            ConcurrencyConflictError: If expected_version is provided and does not match DB version.
            DuplicateEntityError: If an order with the same ID already exists on insert.
        """
        ...


class PaymentRepository(Protocol):
    """Repository port for Payment aggregates."""

    async def get_by_id(self, merchant_id: MerchantId, payment_id: PaymentId) -> Payment | None:
        """Fetch payment attempt by ID scoped by merchant."""
        ...

    async def get_by_order_id(
        self, merchant_id: MerchantId, order_id: OrderId
    ) -> Sequence[Payment]:
        """Fetch all payment attempts for a given order."""
        ...

    async def save(
        self, merchant_id: MerchantId, payment: Payment, expected_version: int | None = None
    ) -> Payment:
        """Persist or update payment attempt with optimistic concurrency check."""
        ...


class RecoveryCaseRepository(Protocol):
    """Repository port for RecoveryCase aggregates."""

    async def get_by_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> RecoveryCase | None:
        """Fetch recovery case by ID scoped by merchant."""
        ...

    async def get_by_payment_id(
        self, merchant_id: MerchantId, payment_id: PaymentId
    ) -> RecoveryCase | None:
        """Fetch recovery case for a specific payment attempt."""
        ...

    async def list_by_state(
        self,
        merchant_id: MerchantId,
        state: RecoveryCaseState,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[RecoveryCase]:
        """List recovery cases in a given state."""
        ...

    async def save(
        self, merchant_id: MerchantId, case: RecoveryCase, expected_version: int | None = None
    ) -> RecoveryCase:
        """Persist or update recovery case with optimistic concurrency check."""
        ...


class RecoveryProposalRepository(Protocol):
    """Repository port for RecoveryProposal entities."""

    async def get_by_id(
        self, merchant_id: MerchantId, proposal_id: RecoveryProposalId
    ) -> RecoveryProposal | None:
        """Fetch recovery proposal by ID scoped by merchant."""
        ...

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryProposal]:
        """Fetch all proposals associated with a recovery case."""
        ...

    async def save(self, merchant_id: MerchantId, proposal: RecoveryProposal) -> RecoveryProposal:
        """Persist a new diagnostic recovery proposal."""
        ...


class PolicyRepository(Protocol):
    """Repository port for merchant Policy aggregates."""

    async def get_by_merchant_id(self, merchant_id: MerchantId) -> Policy | None:
        """Fetch the active guardrail policy for a merchant."""
        ...

    async def get_by_id(self, merchant_id: MerchantId, policy_id: PolicyId) -> Policy | None:
        """Fetch a policy by its ID scoped to merchant."""
        ...

    async def save(
        self, merchant_id: MerchantId, policy: Policy, expected_version: int | None = None
    ) -> Policy:
        """Persist or update merchant policy with optimistic concurrency check."""
        ...


class RecoveryActionRepository(Protocol):
    """Repository port for RecoveryAction aggregates."""

    async def get_by_id(
        self, merchant_id: MerchantId, action_id: RecoveryActionId
    ) -> RecoveryAction | None:
        """Fetch recovery action by ID scoped by merchant."""
        ...

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryAction]:
        """Fetch all actions associated with a recovery case."""
        ...

    async def save(
        self, merchant_id: MerchantId, action: RecoveryAction, expected_version: int | None = None
    ) -> RecoveryAction:
        """Persist or update recovery action with optimistic concurrency check."""
        ...


class RecoveryOutcomeRepository(Protocol):
    """Repository port for RecoveryOutcome entities."""

    async def get_by_action_id(
        self, merchant_id: MerchantId, action_id: RecoveryActionId
    ) -> RecoveryOutcome | None:
        """Fetch recovery outcome by action ID scoped by merchant."""
        ...

    async def list_by_case_id(
        self, merchant_id: MerchantId, case_id: RecoveryCaseId
    ) -> Sequence[RecoveryOutcome]:
        """Fetch all outcomes associated with a recovery case."""
        ...

    async def save(self, merchant_id: MerchantId, outcome: RecoveryOutcome) -> RecoveryOutcome:
        """Persist or update a recovery outcome."""
        ...


class DomainEventRepository(Protocol):
    """Repository port for append-only domain event log."""

    async def append(self, merchant_id: MerchantId | None, event: DomainEvent) -> None:
        """Append an immutable domain event to the log."""
        ...

    async def list_by_aggregate(
        self,
        merchant_id: MerchantId,
        aggregate_type: str,
        aggregate_id: str,
        limit: int = 100,
    ) -> Sequence[DomainEvent]:
        """Fetch domain events for an aggregate in chronological order scoped to merchant."""
        ...
