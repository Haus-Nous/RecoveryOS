"""Multi-tenant data isolation and merchant boundary tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.payment import Payment, PaymentState
from app.domain.entities.policy import Policy
from app.domain.entities.recovery_action import RecoveryAction, RecoveryActionState
from app.domain.entities.recovery_case import RecoveryCase, RecoveryCaseState
from app.domain.entities.recovery_outcome import OutcomeStatus, RecoveryOutcome, VerificationStatus
from app.domain.entities.recovery_proposal import RecoveryProposal, RecoveryStrategy
from app.domain.types import (
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
from app.domain.values.money import Money
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_multi_tenant_isolation_across_all_aggregates(
    session_factory: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)

    # 1. Seed two distinct merchants
    m_a = MerchantModel(
        id="merch_01JTENANTA00000000000000",
        name="Merchant Alpha",
        slug="merchant-alpha",
        created_at=now,
        updated_at=now,
    )
    m_b = MerchantModel(
        id="merch_01JTENANTB00000000000000",
        name="Merchant Beta",
        slug="merchant-beta",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([m_a, m_b])
    await db_session.commit()

    merchant_a = MerchantId(m_a.id)
    merchant_b = MerchantId(m_b.id)

    # 2. Populate resources for Merchant A
    uow_a = SqlAlchemyUnitOfWork(session_factory)
    async with uow_a:
        order_a = Order(
            id=OrderId("ord_01JALPHAORD00000000000000"),
            merchant_id=merchant_a,
            amount=Money.from_minor(100000, Currency.INR),
            status=OrderStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        payment_a = Payment(
            id=PaymentId("pay_01JALPHAPMT00000000000000"),
            merchant_id=merchant_a,
            order_id=order_a.id,
            amount=Money.from_minor(100000, Currency.INR),
            state=PaymentState.FAILED,
            attempt_number=1,
            created_at=now,
            updated_at=now,
        )
        case_a = RecoveryCase(
            id=RecoveryCaseId("case_01JALPHACASE000000000000"),
            merchant_id=merchant_a,
            payment_id=payment_a.id,
            amount_at_risk=Money.from_minor(100000, Currency.INR),
            state=RecoveryCaseState.APPROVED,
            opened_at=now,
            updated_at=now,
        )
        policy_a = Policy(
            id=PolicyId("pol_01JALPHAPOL0000000000000"),
            merchant_id=merchant_a,
            enabled=True,
            max_retry_attempts=3,
            cooldown_seconds=300,
            auto_action_amount_limit=Money.from_minor(500000, Currency.INR),
            review_required_above=Money.from_minor(1000000, Currency.INR),
            allowed_strategies=frozenset({RecoveryStrategy.RETRY_SAME_METHOD}),
            created_at=now,
            updated_at=now,
        )
        prop_a = RecoveryProposal(
            id=RecoveryProposalId("prop_01JALPHAPROP00000000000"),
            recovery_case_id=case_a.id,
            strategy=RecoveryStrategy.RETRY_SAME_METHOD,
            rationale="Alpha proposal",
            confidence=Confidence(basis_points=8000),
            source=ProposalSource.AI,
            created_at=now,
        )
        act_a = RecoveryAction(
            id=RecoveryActionId("act_01JALPHAACT0000000000000"),
            recovery_case_id=case_a.id,
            strategy=RecoveryStrategy.RETRY_SAME_METHOD,
            state=RecoveryActionState.SUCCEEDED,
            authorization_decision=PolicyDecision.ALLOW,
            authorization_reference="ref_a",
            created_at=now,
            updated_at=now,
        )
        out_a = RecoveryOutcome(
            recovery_case_id=case_a.id,
            recovery_action_id=act_a.id,
            status=OutcomeStatus.RECOVERY_OBSERVED,
            amount_recovered=Money.from_minor(100000, Currency.INR),
            observed_at=now,
            verification_status=VerificationStatus.VERIFIED,
            verification_reference="settle_alpha",
            verified_at=now,
        )

        await uow_a.orders.save(merchant_a, order_a)
        await uow_a.payments.save(merchant_a, payment_a)
        await uow_a.recovery_cases.save(merchant_a, case_a)
        await uow_a.policies.save(merchant_a, policy_a)
        await uow_a.recovery_proposals.save(merchant_a, prop_a)
        await uow_a.recovery_actions.save(merchant_a, act_a)
        await uow_a.recovery_outcomes.save(merchant_a, out_a)
        await uow_a.commit()

    # 3. Verify Merchant B cannot read ANY of Merchant A's resources via tenant-scoped repos
    uow_b = SqlAlchemyUnitOfWork(session_factory)
    async with uow_b:
        # Order isolation
        assert await uow_b.orders.get_by_id(merchant_b, order_a.id) is None

        # Payment isolation
        assert await uow_b.payments.get_by_id(merchant_b, payment_a.id) is None
        assert len(await uow_b.payments.get_by_order_id(merchant_b, order_a.id)) == 0

        # Case isolation
        assert await uow_b.recovery_cases.get_by_id(merchant_b, case_a.id) is None
        assert await uow_b.recovery_cases.get_by_payment_id(merchant_b, payment_a.id) is None
        assert (
            len(await uow_b.recovery_cases.list_by_state(merchant_b, RecoveryCaseState.APPROVED))
            == 0
        )

        # Policy isolation
        assert await uow_b.policies.get_by_merchant_id(merchant_b) is None
        assert await uow_b.policies.get_by_id(merchant_b, policy_a.id) is None

        # Proposal isolation
        assert await uow_b.recovery_proposals.get_by_id(merchant_b, prop_a.id) is None
        assert len(await uow_b.recovery_proposals.list_by_case_id(merchant_b, case_a.id)) == 0

        # Action isolation
        assert await uow_b.recovery_actions.get_by_id(merchant_b, act_a.id) is None
        assert len(await uow_b.recovery_actions.list_by_case_id(merchant_b, case_a.id)) == 0

        # Outcome isolation
        assert await uow_b.recovery_outcomes.get_by_action_id(merchant_b, act_a.id) is None
        assert len(await uow_b.recovery_outcomes.list_by_case_id(merchant_b, case_a.id)) == 0


@pytest.mark.asyncio
async def test_cross_merchant_foreign_key_protection(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)

    # Seed merchant Alpha
    await db_session.execute(
        text(
            "INSERT INTO merchants (id, name, slug, created_at, updated_at) "
            "VALUES ('merch_alpha_x', 'Alpha Corp', 'alpha-corp', :now, :now)"
        ),
        {"now": now},
    )
    # Seed order belonging to Alpha
    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_alpha_1', 'merch_alpha_x', 5000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"now": now},
    )
    await db_session.commit()

    # Attempt to insert payment for non-existent merchant Beta referencing Alpha's order -> must fail FK
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
                "VALUES ('pay_beta_cross', 'merch_nonexistent', 'ord_alpha_1', 5000, 'INR', 'FAILED', 1, :now, :now, 1)"
            ),
            {"now": now},
        )
        await db_session.flush()
    await db_session.rollback()
