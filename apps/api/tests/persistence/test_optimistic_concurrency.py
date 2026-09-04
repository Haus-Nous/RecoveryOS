"""Optimistic concurrency control and stale write prevention tests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.exceptions import ConcurrencyConflictError
from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.payment import Payment, PaymentState
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.entities.recovery_proposal import RecoveryStrategy
from app.domain.types import (
    MerchantId,
    OrderId,
    PaymentId,
    PolicyId,
    RecoveryActionId,
    RecoveryCaseId,
)
from app.domain.values.currency import Currency
from app.domain.values.decision import PolicyDecision
from app.domain.values.money import Money
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_order_optimistic_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    now = datetime.now(UTC)

    # 1. Create initial order at version 1
    order = Order(
        id=OrderId("ord_01JCONCUR00000000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(100000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    uow_init = SqlAlchemyUnitOfWork(session_factory)
    async with uow_init:
        await uow_init.orders.save(merchant_id, order)
        await uow_init.commit()

    # 2. Session 1 loads order and updates (expecting version 1 -> commits version 2)
    uow1 = SqlAlchemyUnitOfWork(session_factory)
    async with uow1:
        loaded1 = await uow1.orders.get_by_id(merchant_id, order.id)
        assert loaded1 is not None
        loaded1.transition_to(OrderStatus.OPEN, now)
        loaded1.transition_to(OrderStatus.PAID, now)
        await uow1.orders.save(merchant_id, loaded1, expected_version=1)
        await uow1.commit()

    # 3. Session 2 attempts update with stale expected_version=1 -> MUST FAIL
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        order.transition_to(OrderStatus.CANCELLED, now)
        with pytest.raises(ConcurrencyConflictError) as exc_info:
            await uow2.orders.save(merchant_id, order, expected_version=1)
        assert exc_info.value.entity_type == "Order"
        assert exc_info.value.expected_version == 1


@pytest.mark.asyncio
async def test_payment_optimistic_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    now = datetime.now(UTC)

    uow_init = SqlAlchemyUnitOfWork(session_factory)
    async with uow_init:
        order = Order(
            id=OrderId("ord_01JCONCURPMTORD00000000000"),
            merchant_id=merchant_id,
            amount=Money.from_minor(50000, Currency.INR),
            status=OrderStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        payment = Payment(
            id=PaymentId("pay_01JCONCURPMT00000000000000"),
            merchant_id=merchant_id,
            order_id=order.id,
            amount=Money.from_minor(50000, Currency.INR),
            state=PaymentState.CREATED,
            attempt_number=1,
            created_at=now,
            updated_at=now,
        )
        await uow_init.orders.save(merchant_id, order)
        await uow_init.payments.save(merchant_id, payment)
        await uow_init.commit()

    # Session 1 updates payment state to AUTHORIZED (v1 -> v2)
    uow1 = SqlAlchemyUnitOfWork(session_factory)
    async with uow1:
        loaded = await uow1.payments.get_by_id(merchant_id, payment.id)
        assert loaded is not None
        loaded.transition_to(PaymentState.AUTHORIZED, now)
        await uow1.payments.save(merchant_id, loaded, expected_version=1)
        await uow1.commit()

    # Session 2 tries stale update expecting version 1
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        payment.transition_to(PaymentState.FAILED, now)
        with pytest.raises(ConcurrencyConflictError):
            await uow2.payments.save(merchant_id, payment, expected_version=1)


@pytest.mark.asyncio
async def test_recovery_case_optimistic_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    now = datetime.now(UTC)

    uow_init = SqlAlchemyUnitOfWork(session_factory)
    async with uow_init:
        order = Order(
            id=OrderId("ord_01JCONCURCASEORD0000000000"),
            merchant_id=merchant_id,
            amount=Money.from_minor(75000, Currency.INR),
            status=OrderStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        payment = Payment(
            id=PaymentId("pay_01JCONCURCASEPMT0000000000"),
            merchant_id=merchant_id,
            order_id=order.id,
            amount=Money.from_minor(75000, Currency.INR),
            state=PaymentState.FAILED,
            attempt_number=1,
            created_at=now,
            updated_at=now,
        )
        case = RecoveryCase(
            id=RecoveryCaseId("case_01JCONCURCASE00000000000"),
            merchant_id=merchant_id,
            payment_id=payment.id,
            amount_at_risk=Money.from_minor(75000, Currency.INR),
            state=RecoveryCaseState.OPEN,
            opened_at=now,
            updated_at=now,
        )
        await uow_init.orders.save(merchant_id, order)
        await uow_init.payments.save(merchant_id, payment)
        await uow_init.recovery_cases.save(merchant_id, case)
        await uow_init.commit()

    # Session 1 updates case (v1 -> v2)
    uow1 = SqlAlchemyUnitOfWork(session_factory)
    async with uow1:
        loaded = await uow1.recovery_cases.get_by_id(merchant_id, case.id)
        assert loaded is not None
        loaded.transition_to(RecoveryCaseState.DIAGNOSING, now)
        await uow1.recovery_cases.save(merchant_id, loaded, expected_version=1)
        await uow1.commit()

    # Session 2 tries stale update with v1
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        case.transition_to(RecoveryCaseState.CANCELLED, now, reason="Stale cancel")
        with pytest.raises(ConcurrencyConflictError):
            await uow2.recovery_cases.save(merchant_id, case, expected_version=1)


@pytest.mark.asyncio
async def test_policy_optimistic_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    now = datetime.now(UTC)

    policy = Policy(
        id=PolicyId("pol_01JCONCURPOLICY00000000000"),
        merchant_id=merchant_id,
        enabled=True,
        max_retry_attempts=3,
        cooldown_seconds=300,
        auto_action_amount_limit=Money.from_minor(500000, Currency.INR),
        review_required_above=Money.from_minor(1000000, Currency.INR),
        allowed_strategies=frozenset({RecoveryStrategy.RETRY_SAME_METHOD}),
        created_at=now,
        updated_at=now,
    )
    uow_init = SqlAlchemyUnitOfWork(session_factory)
    async with uow_init:
        await uow_init.policies.save(merchant_id, policy)
        await uow_init.commit()

    # Session 1 updates policy
    uow1 = SqlAlchemyUnitOfWork(session_factory)
    async with uow1:
        loaded = await uow1.policies.get_by_merchant_id(merchant_id)
        assert loaded is not None
        loaded.auto_action_amount_limit = Money.from_minor(600000, Currency.INR)
        loaded.review_required_above = Money.from_minor(1200000, Currency.INR)
        loaded.updated_at = now
        await uow1.policies.save(merchant_id, loaded, expected_version=1)
        await uow1.commit()

    # Session 2 tries stale update
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        policy.enabled = False
        policy.updated_at = now
        with pytest.raises(ConcurrencyConflictError):
            await uow2.policies.save(merchant_id, policy, expected_version=1)


@pytest.mark.asyncio
async def test_recovery_action_optimistic_concurrency(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    now = datetime.now(UTC)

    uow_init = SqlAlchemyUnitOfWork(session_factory)
    async with uow_init:
        order = Order(
            id=OrderId("ord_01JCONCURACTORD00000000000"),
            merchant_id=merchant_id,
            amount=Money.from_minor(100000, Currency.INR),
            status=OrderStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        payment = Payment(
            id=PaymentId("pay_01JCONCURACTPMT0000000000"),
            merchant_id=merchant_id,
            order_id=order.id,
            amount=Money.from_minor(100000, Currency.INR),
            state=PaymentState.FAILED,
            attempt_number=1,
            created_at=now,
            updated_at=now,
        )
        case = RecoveryCase(
            id=RecoveryCaseId("case_01JCONCURACTCASE00000000"),
            merchant_id=merchant_id,
            payment_id=payment.id,
            amount_at_risk=Money.from_minor(100000, Currency.INR),
            state=RecoveryCaseState.APPROVED,
            opened_at=now,
            updated_at=now,
        )
        action = RecoveryAction(
            id=RecoveryActionId("act_01JCONCURACT0000000000000"),
            recovery_case_id=case.id,
            strategy=RecoveryStrategy.RETRY_SAME_METHOD,
            state=RecoveryActionState.PROPOSED,
            created_at=now,
            updated_at=now,
        )
        await uow_init.orders.save(merchant_id, order)
        await uow_init.payments.save(merchant_id, payment)
        await uow_init.recovery_cases.save(merchant_id, case)
        await uow_init.recovery_actions.save(merchant_id, action)
        await uow_init.commit()

    # Session 1 authorizes and queues action (v1 -> v2)
    uow1 = SqlAlchemyUnitOfWork(session_factory)
    async with uow1:
        loaded = await uow1.recovery_actions.get_by_id(merchant_id, action.id)
        assert loaded is not None
        loaded.authorize(PolicyDecision.ALLOW, reference="ref_test", occurred_at=now)
        loaded.transition_to(RecoveryActionState.QUEUED, now)
        await uow1.recovery_actions.save(merchant_id, loaded, expected_version=1)
        await uow1.commit()

    # Session 2 tries stale update
    uow2 = SqlAlchemyUnitOfWork(session_factory)
    async with uow2:
        action.authorize(PolicyDecision.DENY, reference="ref_deny", occurred_at=now)
        with pytest.raises(ConcurrencyConflictError):
            await uow2.recovery_actions.save(merchant_id, action, expected_version=1)
