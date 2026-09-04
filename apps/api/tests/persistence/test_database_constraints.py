"""Direct-SQL and database-level defense-in-depth constraint tests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_order_negative_amount_rejected(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
                "VALUES ('ord_invalid_neg', :merchant_id, -500, 'INR', 'CREATED', :now, :now, 1)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "ck_orders_amount_positive" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_payment_negative_amount_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    # Create valid order first
    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_valid_pmt', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )

    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
                "VALUES ('pay_invalid_neg', :merchant_id, 'ord_valid_pmt', -1000, 'INR', 'FAILED', 1, :now, :now, 1)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "ck_payments_amount_positive" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_recovery_proposal_invalid_confidence_range_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    # Seed order, payment, case
    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_prop_test', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_prop_test', :merchant_id, 'ord_prop_test', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_prop_test', :merchant_id, 'pay_prop_test', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )

    # Insert with confidence_bps = 15000 (> 10000 max)
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO recovery_proposals (id, merchant_id, recovery_case_id, strategy, rationale, confidence_bps, source, created_at) "
                "VALUES ('prop_invalid_conf', :merchant_id, 'case_prop_test', 'SMART_RETRY', 'Reason', 15000, 'AI_MODEL', :now)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "ck_recovery_proposals_confidence_bps_range" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_duplicate_active_recovery_case_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_dup_case', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_dup_case', :merchant_id, 'ord_dup_case', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )

    # First active case
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_active_1', :merchant_id, 'pay_dup_case', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # Second active case for same payment must be rejected by partial unique index
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
                "VALUES ('case_active_2', :merchant_id, 'pay_dup_case', 1000, 'INR', 'DIAGNOSING', :now, :now, 0, 1)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "uq_active_recovery_case_per_payment" in str(exc_info.value)
        or "unique constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_executable_action_without_allow_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_act_inv', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_act_inv', :merchant_id, 'ord_act_inv', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_act_inv', :merchant_id, 'pay_act_inv', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )

    # Insert action with state='EXECUTING' but authorization_decision='DENY' or NULL
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                "VALUES ('act_unauth', :merchant_id, 'case_act_inv', 'SMART_RETRY', 'EXECUTING', 'DENY', 1, :now, :now, 1)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "ck_recovery_actions_executable_must_be_allowed" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_verified_outcome_without_evidence_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_out_inv', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_out_inv', :merchant_id, 'ord_out_inv', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_out_inv', :merchant_id, 'pay_out_inv', 1000, 'INR', 'APPROVED', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
            "VALUES ('act_out_inv', :merchant_id, 'case_out_inv', 'SMART_RETRY', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )

    # Insert outcome with verification_status='VERIFIED' but verification_reference=NULL
    with pytest.raises(IntegrityError) as exc_info:
        await db_session.execute(
            text(
                "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status, verification_reference, verified_at) "
                "VALUES ('out_inv_ev', :merchant_id, 'case_out_inv', 'act_out_inv', 'RECOVERY_OBSERVED', 1000, 'INR', :now, 'VERIFIED', NULL, NULL)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
    assert (
        "ck_recovery_outcomes_verified_requires_evidence" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_duplicate_primary_key_rejected(db_session: AsyncSession, seed_merchant: Any) -> None:
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_pk_test', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
                "VALUES ('ord_pk_test', :merchant_id, 2000, 'INR', 'CREATED', :now, :now, 1)"
            ),
            {"merchant_id": merchant.id, "now": now},
        )
        await db_session.flush()
    await db_session.rollback()
