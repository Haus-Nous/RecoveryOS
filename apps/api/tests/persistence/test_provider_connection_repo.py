"""Tests for ProviderConnectionRepository and database tenant scoping."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.unit_of_work import UnitOfWork
from app.core.exceptions import ConcurrencyError
from app.domain.types import MerchantId
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from app.providers.types import (
    PaymentProviderConnection,
    PaymentProviderName,
    ProviderConnectionStatus,
    ProviderMode,
)


@pytest.fixture
def uow(session_factory: async_sessionmaker[AsyncSession]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session_factory)


@pytest.fixture
async def seeded_merchants(uow: UnitOfWork) -> tuple[MerchantId, MerchantId]:
    """Seed two distinct merchants for tenant isolation testing."""
    m1_id = MerchantId(f"mer_{uuid.uuid4().hex[:16]}")
    m2_id = MerchantId(f"mer_{uuid.uuid4().hex[:16]}")

    async with uow:
        # Access session directly through internal _session attribute for seeding
        session = uow._session  # type: ignore[attr-defined]
        now = datetime.now(UTC)
        m1 = MerchantModel(
            id=str(m1_id),
            name="Merchant Alpha",
            slug=f"merchant-alpha-{m1_id}",
            created_at=now,
            updated_at=now,
        )
        m2 = MerchantModel(
            id=str(m2_id),
            name="Merchant Beta",
            slug=f"merchant-beta-{m2_id}",
            created_at=now,
            updated_at=now,
        )
        session.add(m1)
        session.add(m2)
        await uow.commit()

    return m1_id, m2_id


async def test_provider_connection_crud_and_tenancy(
    uow: UnitOfWork, seeded_merchants: tuple[MerchantId, MerchantId]
) -> None:
    """Verify tenant isolation and lifecycle of PaymentProviderConnection."""
    merchant_a, merchant_b = seeded_merchants
    conn_id = f"conn_{uuid.uuid4().hex[:16]}"
    now = datetime.now(UTC)

    conn_a = PaymentProviderConnection(
        id=conn_id,
        merchant_id=merchant_a,
        provider=PaymentProviderName.RAZORPAY,
        mode=ProviderMode.TEST,
        credential_ref="RAZORPAY_TEST_DEMO",
        status=ProviderConnectionStatus.ACTIVE,
        key_id_fingerprint="rzp_test_...abcd",
        last_verified_at=now,
        created_at=now,
        updated_at=now,
        version=1,
    )

    # 1. Save connection for Merchant A
    async with uow:
        await uow.payment_provider_connections.save(merchant_a, conn_a)
        await uow.commit()

    # 2. Merchant A can read connection
    async with uow:
        fetched = await uow.payment_provider_connections.get_by_id(merchant_a, conn_id)
        assert fetched is not None
        assert fetched.id == conn_id
        assert fetched.merchant_id == merchant_a
        assert fetched.provider == PaymentProviderName.RAZORPAY
        assert fetched.mode == ProviderMode.TEST
        assert fetched.credential_ref == "RAZORPAY_TEST_DEMO"
        assert fetched.status == ProviderConnectionStatus.ACTIVE
        assert fetched.key_id_fingerprint == "rzp_test_...abcd"
        assert fetched.version == 1

    # 3. Merchant B CANNOT read connection (Strict Tenant Scoping)
    async with uow:
        fetched_b = await uow.payment_provider_connections.get_by_id(merchant_b, conn_id)
        assert fetched_b is None

        # Merchant B list does not contain Merchant A's connection
        list_b = await uow.payment_provider_connections.list_for_merchant(merchant_b)
        assert len(list_b) == 0

        # Merchant A list contains it
        list_a = await uow.payment_provider_connections.list_for_merchant(merchant_a)
        assert len(list_a) == 1
        assert list_a[0].id == conn_id

    # 4. Save cross-tenant mismatch fails
    async with uow:
        with pytest.raises(ValueError, match="Tenant isolation violation"):
            await uow.payment_provider_connections.save(merchant_b, conn_a)


async def test_provider_connection_optimistic_locking(
    uow: UnitOfWork, seeded_merchants: tuple[MerchantId, MerchantId]
) -> None:
    """Verify version-based optimistic locking on provider connections."""
    merchant_a, _ = seeded_merchants
    conn_id = f"conn_{uuid.uuid4().hex[:16]}"
    now = datetime.now(UTC)

    conn = PaymentProviderConnection(
        id=conn_id,
        merchant_id=merchant_a,
        provider=PaymentProviderName.RAZORPAY,
        mode=ProviderMode.TEST,
        credential_ref="RAZORPAY_TEST_DEMO",
        status=ProviderConnectionStatus.UNVERIFIED,
        created_at=now,
        updated_at=now,
        version=1,
    )

    async with uow:
        await uow.payment_provider_connections.save(merchant_a, conn)
        await uow.commit()

    # Update version 1 -> 2
    async with uow:
        fetched = await uow.payment_provider_connections.get_by_id(merchant_a, conn_id)
        assert fetched is not None
        updated_conn = PaymentProviderConnection(
            id=fetched.id,
            merchant_id=fetched.merchant_id,
            provider=fetched.provider,
            mode=fetched.mode,
            credential_ref=fetched.credential_ref,
            status=ProviderConnectionStatus.ACTIVE,
            key_id_fingerprint="rzp_test_...fingerprint",
            last_verified_at=datetime.now(UTC),
            created_at=fetched.created_at,
            updated_at=datetime.now(UTC),
            version=fetched.version,
        )
        await uow.payment_provider_connections.save(merchant_a, updated_conn)
        await uow.commit()

    # Stale update with version 1 fails
    stale_conn = PaymentProviderConnection(
        id=conn_id,
        merchant_id=merchant_a,
        provider=PaymentProviderName.RAZORPAY,
        mode=ProviderMode.TEST,
        credential_ref="RAZORPAY_TEST_DEMO",
        status=ProviderConnectionStatus.DISABLED,
        created_at=now,
        updated_at=now,
        version=1,  # Stale! DB is now 2
    )
    async with uow:
        with pytest.raises(ConcurrencyError, match="Optimistic lock violation"):
            await uow.payment_provider_connections.save(merchant_a, stale_conn)


async def test_secret_database_audit(uow: UnitOfWork) -> None:
    """Audit the database schema ensuring zero secret or credential columns exist."""
    async with uow:
        session = uow._session  # type: ignore[attr-defined]

        def check_columns(sync_conn: Any) -> None:
            inspector = inspect(sync_conn)
            columns = [c["name"] for c in inspector.get_columns("payment_provider_connections")]
            prohibited_substrings = [
                "secret",
                "key_secret",
                "api_secret",
                "password",
                "authorization",
                "access_token",
                "refresh_token",
                "raw_credential",
            ]
            for col in columns:
                col_lower = col.lower()
                for prohibited in prohibited_substrings:
                    assert prohibited not in col_lower, (
                        f"Database security audit failed: column '{col}' matches prohibited pattern '{prohibited}'"
                    )

        conn = await session.connection()
        await conn.run_sync(check_columns)
