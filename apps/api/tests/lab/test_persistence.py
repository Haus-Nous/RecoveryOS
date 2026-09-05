"""Tests for safe database persistence of synthetic entities."""

from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.persistence.models.domain_event import DomainEventModel
from app.infrastructure.persistence.models.order import OrderModel
from app.infrastructure.persistence.models.payment import PaymentModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.lab.generator import SyntheticLabGenerator
from app.lab.models import SyntheticLabConfig
from app.lab.persistence import (
    assert_safe_environment,
    persist_synthetic_batch,
    seed_synthetic_merchants,
)


def test_persistence_refused_in_production_and_staging() -> None:
    """Fail-closed check must reject staging and production environments."""
    mock_prod = type("MockSettings", (), {"app_env": "production"})
    with (
        patch("app.lab.persistence.get_settings", return_value=mock_prod),
        pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"),
    ):
        assert_safe_environment()

    mock_stage = type("MockSettings", (), {"app_env": "staging"})
    with (
        patch("app.lab.persistence.get_settings", return_value=mock_stage),
        pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"),
    ):
        assert_safe_environment()


@pytest.mark.asyncio
async def test_synthetic_persistence_to_test_database(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Persisting synthetic records writes Merchant, Order, and Payment, with NO domain_events."""
    config = SyntheticLabConfig(
        seed=777,
        journey_count=5,
        merchant_count=2,
        generation_profile="default",
    )
    generator = SyntheticLabGenerator(config)
    batch = [(j, gt) for j, events, gt in generator.generate_stream()]

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await seed_synthetic_merchants(uow, generator.merchants)
        persisted = await persist_synthetic_batch(uow, batch)
        assert persisted == 5
        await uow.commit()

    # Verify directly via session
    async with session_factory() as session:
        # 1. Orders exist
        for journey, gt in batch:
            stmt = select(OrderModel).where(
                OrderModel.merchant_id == journey.merchant_id,
                OrderModel.id == journey.order_id,
            )
            order_row = (await session.execute(stmt)).scalar_one_or_none()
            assert order_row is not None
            assert order_row.amount_minor == journey.amount_in_cents

            # 2. Payments exist
            for att in gt.attempt_truths:
                p_stmt = select(PaymentModel).where(
                    PaymentModel.merchant_id == journey.merchant_id,
                    PaymentModel.id == att.payment_id,
                )
                payment_row = (await session.execute(p_stmt)).scalar_one_or_none()
                assert payment_row is not None
                assert payment_row.order_id == journey.order_id

        # 3. Amendment 7: Zero synthetic observed events written to domain_events
        evt_stmt = select(DomainEventModel).where(
            DomainEventModel.merchant_id.in_([m.merchant_id for m in generator.merchants])
        )
        domain_evts = (await session.execute(evt_stmt)).scalars().all()
        assert len(domain_evts) == 0, (
            "Synthetic observed events must NOT be persisted to domain_events table"
        )
