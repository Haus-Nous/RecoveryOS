"""Round-trip persistence and domain mapping tests for all entities and aggregates."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.payment import Payment, PaymentState
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.entities.recovery_outcome import OutcomeStatus, RecoveryOutcome, VerificationStatus
from app.domain.entities.recovery_proposal import RecoveryProposal, RecoveryStrategy
from app.domain.events.base import DomainEvent
from app.domain.types import (
    DomainEventId,
    MerchantId,
    OrderId,
    PaymentId,
    PolicyId,
    RecoveryActionId,
    RecoveryCaseId,
    RecoveryProposalId,
)
from app.domain.values.confidence import Confidence
from app.domain.values.currency import Currency
from app.domain.values.decision import PolicyDecision, ProposalSource
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.domain.values.money import Money
from app.infrastructure.persistence.repositories.domain_event_repo import (
    SqlAlchemyDomainEventRepository,
)
from app.infrastructure.persistence.repositories.order_repo import SqlAlchemyOrderRepository
from app.infrastructure.persistence.repositories.payment_repo import SqlAlchemyPaymentRepository
from app.infrastructure.persistence.repositories.policy_repo import SqlAlchemyPolicyRepository
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


@pytest.mark.asyncio
async def test_order_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    repo = SqlAlchemyOrderRepository(db_session)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JROUNDTRIP00000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(499900, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
        external_reference="ext_checkout_123",
    )

    saved = await repo.save(merchant_id, order)
    await db_session.commit()
    assert saved.id == order.id

    fetched = await repo.get_by_id(merchant_id, order.id)
    assert fetched is not None
    assert fetched.id == order.id
    assert fetched.merchant_id == merchant_id
    assert fetched.amount == Money.from_minor(499900, Currency.INR)
    assert fetched.status == OrderStatus.CREATED
    assert fetched.external_reference == "ext_checkout_123"


@pytest.mark.asyncio
async def test_payment_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    order_repo = SqlAlchemyOrderRepository(db_session)
    payment_repo = SqlAlchemyPaymentRepository(db_session)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JPMTORDER000000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(125000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    await order_repo.save(merchant_id, order)

    failure = PaymentFailure(
        category=FailureCategory.AUTHENTICATION_FAILURE,
        code="AUTH_3DS_FAILED",
        reason="Customer did not complete OTP validation",
        is_retryable_hint=True,
        occurred_at=now,
    )
    payment = Payment(
        id=PaymentId("pay_01JPMTTEST000000000000000"),
        merchant_id=merchant_id,
        order_id=order.id,
        amount=Money.from_minor(125000, Currency.INR),
        state=PaymentState.FAILED,
        attempt_number=1,
        created_at=now,
        updated_at=now,
        failure=failure,
        provider_reference="rzp_pay_999",
    )

    await payment_repo.save(merchant_id, payment)
    await db_session.commit()

    fetched = await payment_repo.get_by_id(merchant_id, payment.id)
    assert fetched is not None
    assert fetched.id == payment.id
    assert fetched.state == PaymentState.FAILED
    assert fetched.failure is not None
    assert fetched.failure.category == FailureCategory.AUTHENTICATION_FAILURE
    assert fetched.failure.code == "AUTH_3DS_FAILED"
    assert fetched.failure.is_retryable_hint is True
    assert fetched.provider_reference == "rzp_pay_999"


@pytest.mark.asyncio
async def test_recovery_case_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    order_repo = SqlAlchemyOrderRepository(db_session)
    payment_repo = SqlAlchemyPaymentRepository(db_session)
    case_repo = SqlAlchemyRecoveryCaseRepository(db_session)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JCASEORDER00000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(250000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    await order_repo.save(merchant_id, order)

    payment = Payment(
        id=PaymentId("pay_01JCASEPMT000000000000000"),
        merchant_id=merchant_id,
        order_id=order.id,
        amount=Money.from_minor(250000, Currency.INR),
        state=PaymentState.FAILED,
        attempt_number=1,
        created_at=now,
        updated_at=now,
    )
    await payment_repo.save(merchant_id, payment)

    case = RecoveryCase(
        id=RecoveryCaseId("case_01JCASETEST00000000000000"),
        merchant_id=merchant_id,
        payment_id=payment.id,
        amount_at_risk=Money.from_minor(250000, Currency.INR),
        state=RecoveryCaseState.OPEN,
        opened_at=now,
        updated_at=now,
        attempt_count=0,
    )
    await case_repo.save(merchant_id, case)
    await db_session.commit()

    fetched = await case_repo.get_by_id(merchant_id, case.id)
    assert fetched is not None
    assert fetched.id == case.id
    assert fetched.state == RecoveryCaseState.OPEN
    assert fetched.amount_at_risk == Money.from_minor(250000, Currency.INR)

    # Fetch by payment ID
    by_payment = await case_repo.get_by_payment_id(merchant_id, payment.id)
    assert by_payment is not None
    assert by_payment.id == case.id


@pytest.mark.asyncio
async def test_recovery_proposal_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    order_repo = SqlAlchemyOrderRepository(db_session)
    payment_repo = SqlAlchemyPaymentRepository(db_session)
    case_repo = SqlAlchemyRecoveryCaseRepository(db_session)
    prop_repo = SqlAlchemyRecoveryProposalRepository(db_session)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JPROPORD0000000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(50000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    await order_repo.save(merchant_id, order)

    payment = Payment(
        id=PaymentId("pay_01JPROPPMT0000000000000000"),
        merchant_id=merchant_id,
        order_id=order.id,
        amount=Money.from_minor(50000, Currency.INR),
        state=PaymentState.FAILED,
        attempt_number=1,
        created_at=now,
        updated_at=now,
    )
    await payment_repo.save(merchant_id, payment)

    case = RecoveryCase(
        id=RecoveryCaseId("case_01JPROPCASET0000000000000"),
        merchant_id=merchant_id,
        payment_id=payment.id,
        amount_at_risk=Money.from_minor(50000, Currency.INR),
        state=RecoveryCaseState.DIAGNOSING,
        opened_at=now,
        updated_at=now,
    )
    await case_repo.save(merchant_id, case)

    proposal = RecoveryProposal(
        id=RecoveryProposalId("prop_01JPROPTEST00000000000000"),
        recovery_case_id=case.id,
        strategy=RecoveryStrategy.RETRY_SAME_METHOD,
        rationale="Transient gateway timeout with 85% success probability",
        confidence=Confidence(basis_points=8500),
        source=ProposalSource.AI,
        created_at=now,
    )
    await prop_repo.save(merchant_id, proposal)
    await db_session.commit()

    fetched = await prop_repo.get_by_id(merchant_id, proposal.id)
    assert fetched is not None
    assert fetched.id == proposal.id
    assert fetched.strategy == RecoveryStrategy.RETRY_SAME_METHOD
    assert fetched.confidence.basis_points == 8500
    assert fetched.source == ProposalSource.AI


@pytest.mark.asyncio
async def test_policy_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    policy_repo = SqlAlchemyPolicyRepository(db_session)

    now = datetime.now(UTC)
    policy = Policy(
        id=PolicyId("pol_01JPOLICYTEST000000000000"),
        merchant_id=merchant_id,
        enabled=True,
        max_retry_attempts=4,
        cooldown_seconds=180,
        auto_action_amount_limit=Money.from_minor(1000000, Currency.INR),
        review_required_above=Money.from_minor(2000000, Currency.INR),
        allowed_strategies=frozenset(
            {RecoveryStrategy.RETRY_SAME_METHOD, RecoveryStrategy.CREATE_PAYMENT_LINK}
        ),
        created_at=now,
        updated_at=now,
    )
    await policy_repo.save(merchant_id, policy)
    await db_session.commit()

    fetched = await policy_repo.get_by_merchant_id(merchant_id)
    assert fetched is not None
    assert fetched.id == policy.id
    assert fetched.max_retry_attempts == 4
    assert fetched.cooldown_seconds == 180
    assert fetched.auto_action_amount_limit == Money.from_minor(1000000, Currency.INR)
    assert RecoveryStrategy.RETRY_SAME_METHOD in fetched.allowed_strategies


@pytest.mark.asyncio
async def test_recovery_action_and_outcome_roundtrip(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    order_repo = SqlAlchemyOrderRepository(db_session)
    payment_repo = SqlAlchemyPaymentRepository(db_session)
    case_repo = SqlAlchemyRecoveryCaseRepository(db_session)
    action_repo = SqlAlchemyRecoveryActionRepository(db_session)
    outcome_repo = SqlAlchemyRecoveryOutcomeRepository(db_session)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JACTORD00000000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(750000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    await order_repo.save(merchant_id, order)

    payment = Payment(
        id=PaymentId("pay_01JACTPMT00000000000000000"),
        merchant_id=merchant_id,
        order_id=order.id,
        amount=Money.from_minor(750000, Currency.INR),
        state=PaymentState.FAILED,
        attempt_number=1,
        created_at=now,
        updated_at=now,
    )
    await payment_repo.save(merchant_id, payment)

    case = RecoveryCase(
        id=RecoveryCaseId("case_01JACTCASE000000000000000"),
        merchant_id=merchant_id,
        payment_id=payment.id,
        amount_at_risk=Money.from_minor(750000, Currency.INR),
        state=RecoveryCaseState.APPROVED,
        opened_at=now,
        updated_at=now,
    )
    await case_repo.save(merchant_id, case)

    action = RecoveryAction(
        id=RecoveryActionId("act_01JACTTEST000000000000000"),
        recovery_case_id=case.id,
        strategy=RecoveryStrategy.RETRY_SAME_METHOD,
        state=RecoveryActionState.SUCCEEDED,
        created_at=now,
        updated_at=now,
        authorization_decision=PolicyDecision.ALLOW,
        authorization_reference="pol_auto_approved",
        attempt_number=1,
    )
    await action_repo.save(merchant_id, action)

    outcome = RecoveryOutcome(
        recovery_case_id=case.id,
        recovery_action_id=action.id,
        status=OutcomeStatus.RECOVERY_OBSERVED,
        amount_recovered=Money.from_minor(750000, Currency.INR),
        observed_at=now,
        verification_status=VerificationStatus.VERIFIED,
        verification_reference="settlement_bank_txn_888",
        verified_at=now,
    )
    await outcome_repo.save(merchant_id, outcome)
    await db_session.commit()

    fetched_action = await action_repo.get_by_id(merchant_id, action.id)
    assert fetched_action is not None
    assert fetched_action.state == RecoveryActionState.SUCCEEDED
    assert fetched_action.authorization_decision == PolicyDecision.ALLOW

    fetched_outcome = await outcome_repo.get_by_action_id(merchant_id, action.id)
    assert fetched_outcome is not None
    assert fetched_outcome.status == OutcomeStatus.RECOVERY_OBSERVED
    assert fetched_outcome.verification_status == VerificationStatus.VERIFIED
    assert fetched_outcome.verification_reference == "settlement_bank_txn_888"


@pytest.mark.asyncio
async def test_domain_event_roundtrip(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    event_repo = SqlAlchemyDomainEventRepository(db_session)

    now = datetime.now(UTC)
    event = DomainEvent(
        event_id=DomainEventId("evt_01JEVTTEST000000000000000"),
        event_type="PaymentFailureDetected",
        aggregate_type="Payment",
        aggregate_id="pay_01JEVTPMT00000000000000000",
        occurred_at=now,
        payload={"merchant_id": str(merchant_id), "amount_minor": 10000, "currency": "INR"},
    )

    await event_repo.append(merchant_id, event)
    await db_session.commit()

    events = await event_repo.list_by_aggregate("Payment", "pay_01JEVTPMT00000000000000000")
    assert len(events) == 1
    assert events[0].event_id == event.event_id
    assert events[0].event_type == "PaymentFailureDetected"
    assert events[0].payload["amount_minor"] == 10000
