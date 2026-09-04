"""Transactional boundary and Unit of Work atomicity tests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.order import Order, OrderStatus
from app.domain.events.base import DomainEvent
from app.domain.types import DomainEventId, MerchantId, OrderId
from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.infrastructure.persistence.models.domain_event import DomainEventModel
from app.infrastructure.persistence.models.order import OrderModel
from app.infrastructure.persistence.models.outbox import OutboxMessageModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_uow_successful_commit_atomicity(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    uow = SqlAlchemyUnitOfWork(session_factory)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JUOWCOMMIT00000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(300000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    event = DomainEvent(
        event_id=DomainEventId("evt_01JUOWCOMMIT00000000000000"),
        event_type="OrderCreated",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        occurred_at=now,
        payload={"amount_minor": 300000, "currency": "INR"},
    )

    async with uow:
        await uow.orders.save(merchant_id, order)
        uow.track_event(merchant_id, event)
        await uow.commit()

    # Verify across a separate session that Order, DomainEvent, and Outbox are ALL committed
    async with session_factory() as verify_session:
        order_res = await verify_session.execute(
            select(OrderModel).where(OrderModel.id == str(order.id))
        )
        assert order_res.scalar_one_or_none() is not None

        event_res = await verify_session.execute(
            select(DomainEventModel).where(DomainEventModel.event_id == str(event.event_id))
        )
        assert event_res.scalar_one_or_none() is not None

        outbox_res = await verify_session.execute(
            select(OutboxMessageModel).where(OutboxMessageModel.event_id == str(event.event_id))
        )
        outbox_msg = outbox_res.scalar_one_or_none()
        assert outbox_msg is not None
        assert outbox_msg.event_type == "OrderCreated"
        assert outbox_msg.published_at is None


@pytest.mark.asyncio
async def test_uow_rollback_on_exception(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    uow = SqlAlchemyUnitOfWork(session_factory)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JUOWROLLBACK000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(150000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )
    event = DomainEvent(
        event_id=DomainEventId("evt_01JUOWROLLBACK000000000000"),
        event_type="OrderCreated",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        occurred_at=now,
        payload={"amount_minor": 150000, "currency": "INR"},
    )

    with pytest.raises(RuntimeError, match="Intentional failure inside transaction"):
        async with uow:
            await uow.orders.save(merchant_id, order)
            uow.track_event(merchant_id, event)
            raise RuntimeError("Intentional failure inside transaction")

    # Verify that NONE of the records exist in the database
    async with session_factory() as verify_session:
        order_res = await verify_session.execute(
            select(OrderModel).where(OrderModel.id == str(order.id))
        )
        assert order_res.scalar_one_or_none() is None

        event_res = await verify_session.execute(
            select(DomainEventModel).where(DomainEventModel.event_id == str(event.event_id))
        )
        assert event_res.scalar_one_or_none() is None

        outbox_res = await verify_session.execute(
            select(OutboxMessageModel).where(OutboxMessageModel.event_id == str(event.event_id))
        )
        assert outbox_res.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_repositories_do_not_autocommit(
    session_factory: async_sessionmaker[AsyncSession],
    seed_merchant: Any,
) -> None:
    merchant = await seed_merchant()
    merchant_id = MerchantId(merchant.id)
    uow = SqlAlchemyUnitOfWork(session_factory)

    now = datetime.now(UTC)
    order = Order(
        id=OrderId("ord_01JNOAUTOCOMMIT000000000000"),
        merchant_id=merchant_id,
        amount=Money.from_minor(80000, Currency.INR),
        status=OrderStatus.CREATED,
        created_at=now,
        updated_at=now,
    )

    async with uow:
        await uow.orders.save(merchant_id, order)
        # We explicitly DO NOT call uow.commit()

    # Verify that without commit(), nothing was persisted
    async with session_factory() as verify_session:
        order_res = await verify_session.execute(
            select(OrderModel).where(OrderModel.id == str(order.id))
        )
        assert order_res.scalar_one_or_none() is None
