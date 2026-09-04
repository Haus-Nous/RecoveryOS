"""Direct-SQL and database-level defense-in-depth constraint tests."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_order_amount_constraints_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """Order amount must be strictly positive (reject 0 and negative)."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    # 1. Zero amount rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
                    "VALUES ('ord_zero', :merchant_id, 0, 'INR', 'CREATED', :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. Negative amount rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
                    "VALUES ('ord_neg', :merchant_id, -500, 'INR', 'CREATED', :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_payment_amount_constraints_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """Payment amount must be strictly positive (reject 0 and negative)."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_pmt_chk', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. Zero amount rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
                    "VALUES ('pay_zero', :merchant_id, 'ord_pmt_chk', 0, 'INR', 'FAILED', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. Negative amount rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
                    "VALUES ('pay_neg', :merchant_id, 'ord_pmt_chk', -1000, 'INR', 'FAILED', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_recovery_case_amount_constraints_rejected(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """RecoveryCase amount_at_risk must be strictly positive."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_case_chk', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_case_chk', :merchant_id, 'ord_case_chk', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. Zero amount at risk rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
                    "VALUES ('case_zero', :merchant_id, 'pay_case_chk', 0, 'INR', 'OPEN', :now, :now, 0, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. Negative amount at risk rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
                    "VALUES ('case_neg', :merchant_id, 'pay_case_chk', -500, 'INR', 'OPEN', :now, :now, 0, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_recovery_outcome_amount_constraint(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """RecoveryOutcome recovered amount cannot be negative."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_out_amt', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_out_amt', :merchant_id, 'ord_out_amt', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_out_amt', :merchant_id, 'pay_out_amt', 1000, 'INR', 'APPROVED', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
            "VALUES ('act_out_amt', :merchant_id, 'case_out_amt', 'RETRY_SAME_METHOD', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # Negative amount recovered rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status) "
                    "VALUES ('out_neg', :merchant_id, 'case_out_amt', 'act_out_amt', 'FAILED', -100, 'INR', :now, 'UNVERIFIED')"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_policy_constraints_matrix(db_session: AsyncSession, seed_merchant: Any) -> None:
    """Policy thresholds and retry limits must satisfy check constraints."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    # 1. Negative max_retry_attempts rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO policies (id, merchant_id, enabled, max_retry_attempts, cooldown_seconds, auto_action_amount_limit_minor, review_required_above_minor, currency, allowed_strategies, created_at, updated_at, version) "
                    "VALUES ('pol_neg_retry', :merchant_id, true, -1, 300, 1000, 2000, 'INR', '[\"RETRY_SAME_METHOD\"]', :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. Negative cooldown rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO policies (id, merchant_id, enabled, max_retry_attempts, cooldown_seconds, auto_action_amount_limit_minor, review_required_above_minor, currency, allowed_strategies, created_at, updated_at, version) "
                    "VALUES ('pol_neg_cd', :merchant_id, true, 3, -10, 1000, 2000, 'INR', '[\"RETRY_SAME_METHOD\"]', :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 3. auto_action > review_required rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO policies (id, merchant_id, enabled, max_retry_attempts, cooldown_seconds, auto_action_amount_limit_minor, review_required_above_minor, currency, allowed_strategies, created_at, updated_at, version) "
                    "VALUES ('pol_invalid_ratio', :merchant_id, true, 3, 300, 50000, 10000, 'INR', '[\"RETRY_SAME_METHOD\"]', :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_confidence_constraints_matrix(db_session: AsyncSession, seed_merchant: Any) -> None:
    """Confidence basis points range: [-1 -> reject, 0 -> accept, 10000 -> accept, 10001 -> reject]."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_conf_chk', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_conf_chk', :merchant_id, 'ord_conf_chk', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_conf_chk', :merchant_id, 'pay_conf_chk', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. Negative bps (-1) rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_proposals (id, merchant_id, recovery_case_id, strategy, rationale, confidence_bps, source, created_at) "
                    "VALUES ('prop_neg_conf', :merchant_id, 'case_conf_chk', 'RETRY_SAME_METHOD', 'Reason', -1, 'AI', :now)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. Exceeding max bps (10001) rejected
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_proposals (id, merchant_id, recovery_case_id, strategy, rationale, confidence_bps, source, created_at) "
                    "VALUES ('prop_high_conf', :merchant_id, 'case_conf_chk', 'RETRY_SAME_METHOD', 'Reason', 10001, 'AI', :now)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 3. Valid boundary values (0 and 10000) accepted
    await db_session.execute(
        text(
            "INSERT INTO recovery_proposals (id, merchant_id, recovery_case_id, strategy, rationale, confidence_bps, source, created_at) "
            "VALUES ('prop_0_conf', :merchant_id, 'case_conf_chk', 'RETRY_SAME_METHOD', 'Reason 0', 0, 'AI', :now), "
            "       ('prop_10k_conf', :merchant_id, 'case_conf_chk', 'RETRY_SAME_METHOD', 'Reason 10k', 10000, 'AI', :now)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_action_authorization_matrix(db_session: AsyncSession, seed_merchant: Any) -> None:
    """Executable actions (QUEUED, EXECUTING) must strictly require authorization_decision='ALLOW'."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_act_mat', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_act_mat', :merchant_id, 'ord_act_mat', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_act_mat', :merchant_id, 'pay_act_mat', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. QUEUED + REVIEW -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                    "VALUES ('act_q_rev', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'QUEUED', 'REVIEW', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. QUEUED + DENY -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                    "VALUES ('act_q_deny', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'QUEUED', 'DENY', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 3. EXECUTING + REVIEW -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                    "VALUES ('act_ex_rev', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'EXECUTING', 'REVIEW', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 4. EXECUTING + DENY -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                    "VALUES ('act_ex_deny', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'EXECUTING', 'DENY', 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 5. EXECUTING + NULL -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
                    "VALUES ('act_ex_null', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'EXECUTING', NULL, 1, :now, :now, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 6. Valid: AUTHORIZED / QUEUED / EXECUTING + ALLOW -> accept
    await db_session.execute(
        text(
            "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
            "VALUES ('act_auth_ok', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'AUTHORIZED', 'ALLOW', 1, :now, :now, 1), "
            "       ('act_q_ok', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'QUEUED', 'ALLOW', 1, :now, :now, 1), "
            "       ('act_ex_ok', :merchant_id, 'case_act_mat', 'RETRY_SAME_METHOD', 'EXECUTING', 'ALLOW', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_verification_constraints_matrix(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """Outcome verification requires status=RECOVERY_OBSERVED, evidence reference, and timestamp."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_ver_mat', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_ver_mat', :merchant_id, 'ord_ver_mat', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_ver_mat', :merchant_id, 'pay_ver_mat', 1000, 'INR', 'APPROVED', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO recovery_actions (id, merchant_id, recovery_case_id, strategy, state, authorization_decision, attempt_number, created_at, updated_at, version) "
            "VALUES ('act_ver_mat_1', :merchant_id, 'case_ver_mat', 'RETRY_SAME_METHOD', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1), "
            "       ('act_ver_mat_2', :merchant_id, 'case_ver_mat', 'RETRY_SAME_METHOD', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1), "
            "       ('act_ver_mat_3', :merchant_id, 'case_ver_mat', 'RETRY_SAME_METHOD', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1), "
            "       ('act_ver_mat_ok', :merchant_id, 'case_ver_mat', 'RETRY_SAME_METHOD', 'SUCCEEDED', 'ALLOW', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. VERIFIED + evidence_reference = NULL -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status, verification_reference, verified_at) "
                    "VALUES ('out_v_no_ev', :merchant_id, 'case_ver_mat', 'act_ver_mat_1', 'RECOVERY_OBSERVED', 1000, 'INR', :now, 'VERIFIED', NULL, :now)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 2. VERIFIED + verified_at = NULL -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status, verification_reference, verified_at) "
                    "VALUES ('out_v_no_ts', :merchant_id, 'case_ver_mat', 'act_ver_mat_2', 'RECOVERY_OBSERVED', 1000, 'INR', :now, 'VERIFIED', 'ref_123', NULL)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 3. VERIFIED + status = 'NO_EFFECT' (not RECOVERY_OBSERVED) -> reject
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status, verification_reference, verified_at) "
                    "VALUES ('out_v_bad_st', :merchant_id, 'case_ver_mat', 'act_ver_mat_3', 'NO_EFFECT', 0, 'INR', :now, 'VERIFIED', 'ref_123', :now)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 4. Valid VERIFIED outcome -> accept
    await db_session.execute(
        text(
            "INSERT INTO recovery_outcomes (id, merchant_id, recovery_case_id, recovery_action_id, status, amount_recovered_minor, currency, observed_at, verification_status, verification_reference, verified_at) "
            "VALUES ('out_v_ok', :merchant_id, 'case_ver_mat', 'act_ver_mat_ok', 'RECOVERY_OBSERVED', 1000, 'INR', :now, 'VERIFIED', 'bank_settle_ref', :now)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_active_recovery_case_partial_unique_index(
    db_session: AsyncSession, seed_merchant: Any
) -> None:
    """Only one active case per payment is permitted; historical terminal cases permit new cases."""
    merchant = await seed_merchant()
    now = datetime.now(UTC)

    await db_session.execute(
        text(
            "INSERT INTO orders (id, merchant_id, amount_minor, currency, status, created_at, updated_at, version) "
            "VALUES ('ord_idx_case', :merchant_id, 1000, 'INR', 'CREATED', :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.execute(
        text(
            "INSERT INTO payments (id, merchant_id, order_id, amount_minor, currency, state, attempt_number, created_at, updated_at, version) "
            "VALUES ('pay_idx_case', :merchant_id, 'ord_idx_case', 1000, 'INR', 'FAILED', 1, :now, :now, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 1. Insert first active case
    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_act_1', :merchant_id, 'pay_idx_case', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()

    # 2. Insert second active case for SAME payment -> must be rejected by partial unique index
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
                    "VALUES ('case_act_2', :merchant_id, 'pay_idx_case', 1000, 'INR', 'DIAGNOSING', :now, :now, 0, 1)"
                ),
                {"merchant_id": merchant.id, "now": now},
            )
            await db_session.flush()

    # 3. Transition historical case to terminal state (CANCELLED), then insert new active case -> must SUCCEED
    await db_session.execute(
        text("UPDATE recovery_cases SET state = 'CANCELLED' WHERE id = 'case_act_1'")
    )
    await db_session.flush()

    await db_session.execute(
        text(
            "INSERT INTO recovery_cases (id, merchant_id, payment_id, amount_at_risk_minor, currency, state, opened_at, updated_at, attempt_count, version) "
            "VALUES ('case_new_active', :merchant_id, 'pay_idx_case', 1000, 'INR', 'OPEN', :now, :now, 0, 1)"
        ),
        {"merchant_id": merchant.id, "now": now},
    )
    await db_session.flush()
