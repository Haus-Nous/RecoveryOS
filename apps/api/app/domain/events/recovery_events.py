"""Recovery lifecycle domain events."""

from datetime import datetime

from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.events.base import DomainEvent
from app.domain.types import (
    MerchantId,
    PaymentId,
    RecoveryActionId,
    RecoveryCaseId,
    RecoveryProposalId,
)
from app.domain.values.confidence import Confidence
from app.domain.values.decision import PolicyDecision, ProposalSource
from app.domain.values.money import Money


class RecoveryCaseOpened(DomainEvent):
    """Fired when revenue-loss is detected and a case is opened."""

    @classmethod
    def from_case(
        cls,
        case_id: RecoveryCaseId,
        payment_id: PaymentId,
        merchant_id: MerchantId,
        amount_at_risk: Money,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryCaseOpened",
            aggregate_id=str(case_id),
            aggregate_type="RecoveryCase",
            occurred_at=occurred_at,
            payload={
                "recovery_case_id": str(case_id),
                "payment_id": str(payment_id),
                "merchant_id": str(merchant_id),
                "amount_at_risk_minor": amount_at_risk.amount_minor,
                "currency": amount_at_risk.currency.value,
            },
        )


class RecoveryProposalCreated(DomainEvent):
    """Fired when a recovery strategy is proposed."""

    @classmethod
    def from_proposal(
        cls,
        proposal_id: RecoveryProposalId,
        case_id: RecoveryCaseId,
        strategy: RecoveryStrategy,
        confidence: Confidence,
        source: ProposalSource,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryProposalCreated",
            aggregate_id=str(case_id),
            aggregate_type="RecoveryCase",
            occurred_at=occurred_at,
            payload={
                "proposal_id": str(proposal_id),
                "recovery_case_id": str(case_id),
                "strategy": strategy.value,
                "confidence_bps": confidence.basis_points,
                "source": source.value,
            },
        )


class RecoveryActionAuthorized(DomainEvent):
    """Fired when a recovery action is deterministic-policy authorized."""

    @classmethod
    def from_action(
        cls,
        action_id: RecoveryActionId,
        case_id: RecoveryCaseId,
        strategy: RecoveryStrategy,
        reference: str,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryActionAuthorized",
            aggregate_id=str(action_id),
            aggregate_type="RecoveryAction",
            occurred_at=occurred_at,
            payload={
                "recovery_action_id": str(action_id),
                "recovery_case_id": str(case_id),
                "strategy": strategy.value,
                "authorization_decision": PolicyDecision.ALLOW.value,
                "authorization_reference": reference,
            },
        )


class RecoveryActionDenied(DomainEvent):
    """Fired when a recovery action is denied by policy."""

    @classmethod
    def from_action(
        cls,
        action_id: RecoveryActionId,
        case_id: RecoveryCaseId,
        strategy: RecoveryStrategy,
        reference: str,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryActionDenied",
            aggregate_id=str(action_id),
            aggregate_type="RecoveryAction",
            occurred_at=occurred_at,
            payload={
                "recovery_action_id": str(action_id),
                "recovery_case_id": str(case_id),
                "strategy": strategy.value,
                "authorization_decision": PolicyDecision.DENY.value,
                "authorization_reference": reference,
            },
        )


class RecoveryOutcomeRecorded(DomainEvent):
    """Fired when an action result is observed."""

    @classmethod
    def from_outcome(
        cls,
        case_id: RecoveryCaseId,
        action_id: RecoveryActionId,
        status: str,
        amount_recovered: Money,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryOutcomeRecorded",
            aggregate_id=str(case_id),
            aggregate_type="RecoveryCase",
            occurred_at=occurred_at,
            payload={
                "recovery_case_id": str(case_id),
                "recovery_action_id": str(action_id),
                "outcome_status": status,
                "amount_recovered_minor": amount_recovered.amount_minor,
                "currency": amount_recovered.currency.value,
            },
        )


class RecoveryVerified(DomainEvent):
    """Fired when recovered revenue is verified by settlement/ledger evidence."""

    @classmethod
    def from_verification(
        cls,
        case_id: RecoveryCaseId,
        action_id: RecoveryActionId,
        verified_amount: Money,
        evidence_ref: str,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryVerified",
            aggregate_id=str(case_id),
            aggregate_type="RecoveryCase",
            occurred_at=occurred_at,
            payload={
                "recovery_case_id": str(case_id),
                "recovery_action_id": str(action_id),
                "verified_amount_minor": verified_amount.amount_minor,
                "currency": verified_amount.currency.value,
                "evidence_ref": evidence_ref,
            },
        )


class RecoveryVerificationFailed(DomainEvent):
    """Fired when settlement verification fails or is rejected."""

    @classmethod
    def from_failure(
        cls,
        case_id: RecoveryCaseId,
        action_id: RecoveryActionId,
        reason: str,
        occurred_at: datetime,
    ) -> DomainEvent:
        return DomainEvent.create(
            event_type="RecoveryVerificationFailed",
            aggregate_id=str(case_id),
            aggregate_type="RecoveryCase",
            occurred_at=occurred_at,
            payload={
                "recovery_case_id": str(case_id),
                "recovery_action_id": str(action_id),
                "reason": reason,
            },
        )
