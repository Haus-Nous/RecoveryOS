"""Versioned Catalog of 22 Deterministic Laboratory Scenarios."""

from datetime import datetime, timedelta

from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.payment import Payment, PaymentState
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.failure import FailureCategory, PaymentFailure
from app.lab.models import (
    AttemptGroundTruth,
    GroundTruth,
    SyntheticObservedEvent,
    SyntheticPaymentJourney,
)
from app.lab.scenarios.base import (
    ScenarioContext,
    ScenarioDefinition,
)
from app.lab.types import (
    PaymentMethod,
    Recoverability,
    RecoveryStrategyClass,
    SyntheticEventType,
    SyntheticFailureCategory,
)

ALL_METHODS = frozenset(PaymentMethod)
CARD_AND_NETBANKING = frozenset({PaymentMethod.CARD, PaymentMethod.NETBANKING})
CARD_AND_UPI = frozenset({PaymentMethod.CARD, PaymentMethod.UPI})
CARDS_UPI_WALLET = frozenset({PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.WALLET})
NON_EMI_METHODS = frozenset(
    {PaymentMethod.CARD, PaymentMethod.UPI, PaymentMethod.NETBANKING, PaymentMethod.WALLET}
)
UPI_ONLY = frozenset({PaymentMethod.UPI})
CARD_ONLY = frozenset({PaymentMethod.CARD})


def _make_instrument_ref(method: PaymentMethod, journey_suffix: str) -> str:
    """Generate safe, unmistakably synthetic instrument reference."""
    return f"syn_inst_{method.value.lower()}_{journey_suffix}"


def _format_event_time(dt: datetime) -> str:
    """Format datetime as canonical ISO 8601 UTC string."""
    return dt.isoformat()


# -------------------------------------------------------------------------
# S01: Immediate Success
# -------------------------------------------------------------------------
def _gen_s01(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    # True lifecycle
    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    payment = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=3)
    payment.mark_authorized(t2)
    t3 = t2 + timedelta(seconds=2)
    payment.capture(t3)
    order.mark_paid(t3)

    # Observed events
    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_AUTHORIZED,
            occurred_at=_format_event_time(t2),
            emitted_at=_format_event_time(t2),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "AUTHORIZED",
                "attempt_number": 1,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t3),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 1,
            },
        ),
    ]

    attempt_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Payment captured cleanly on first attempt",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S01",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Clean first attempt capture",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[attempt_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t3),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# Helper for 2-attempt Retry Scenarios (e.g. S02, S03, S06, S11, S12, S21)
# -------------------------------------------------------------------------
def _gen_two_attempt_retry_success(
    ctx: ScenarioContext,
    scenario_id: str,
    failure_cat: SyntheticFailureCategory,
    failure_code: str,
    root_cause_att1: str,
    recoverability: Recoverability,
    strategy: RecoveryStrategyClass,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p1_id = f"{ctx.order_id}_p1"
    p2_id = f"{ctx.order_id}_p2"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    # Attempt 1 fails
    p1 = Payment(
        id=PaymentId(p1_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=5)
    failure = PaymentFailure(
        category=FailureCategory.SOFT_DECLINE
        if failure_cat == SyntheticFailureCategory.ISSUER_DECLINE
        else FailureCategory.NETWORK_ERROR,
        code=failure_code,
        reason=root_cause_att1,
        is_retryable_hint=True,
        occurred_at=t2,
    )
    p1.fail(failure, t2)

    # Attempt 2 retries and succeeds
    t3 = t2 + timedelta(seconds=60)
    p2 = Payment(
        id=PaymentId(p2_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=2,
        created_at=t3,
        updated_at=t3,
    )
    t4 = t3 + timedelta(seconds=4)
    p2.mark_authorized(t4)
    t5 = t4 + timedelta(seconds=2)
    p2.capture(t5)
    order.mark_paid(t5)

    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_FAILED,
            occurred_at=_format_event_time(t2),
            emitted_at=_format_event_time(t2),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "FAILED",
                "attempt_number": 1,
                "error_code": failure_code,
                "error_description": root_cause_att1,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t3),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 2,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_05",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_AUTHORIZED,
            occurred_at=_format_event_time(t4),
            emitted_at=_format_event_time(t4),
            sequence_number=5,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "AUTHORIZED",
                "attempt_number": 2,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_06",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t5),
            emitted_at=_format_event_time(t5),
            sequence_number=6,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 2,
            },
        ),
    ]

    att1_truth = AttemptGroundTruth(
        payment_id=p1_id,
        attempt_number=1,
        expected_final_state="FAILED",
        failure_category=failure_cat,
        failure_code=failure_code,
        root_cause=root_cause_att1,
        is_retryable=True,
        recoverability=recoverability,
    )
    att2_truth = AttemptGroundTruth(
        payment_id=p2_id,
        attempt_number=2,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Retry succeeded cleanly",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id=scenario_id,
        failure_category=failure_cat,
        failure_code=failure_code,
        root_cause=root_cause_att1,
        recoverability=recoverability,
        expected_recovery_strategy_class=strategy,
        expected_recovery_possible=True,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=2,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=True,
        should_open_recovery_case=True,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att1_truth, att2_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p1_id, p2_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t5),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# Helper for Permanent Failure Scenarios (e.g. S04, S08, S09, S10, S14, S22)
# -------------------------------------------------------------------------
def _gen_permanent_failure(
    ctx: ScenarioContext,
    scenario_id: str,
    failure_cat: SyntheticFailureCategory,
    failure_code: str,
    root_cause: str,
    strategy: RecoveryStrategyClass,
    attempts: int = 1,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    payment_ids: list[str] = []
    events: list[SyntheticObservedEvent] = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        )
    ]

    attempt_truths: list[AttemptGroundTruth] = []
    curr_t = t1
    seq = 2

    for att in range(1, attempts + 1):
        p_id = f"{ctx.order_id}_p{att}"
        payment_ids.append(p_id)
        p = Payment(
            id=PaymentId(p_id),
            merchant_id=MerchantId(ctx.merchant_id),
            order_id=OrderId(ctx.order_id),
            amount=ctx.amount,
            state=PaymentState.CREATED,
            attempt_number=att,
            created_at=curr_t,
            updated_at=curr_t,
        )
        events.append(
            SyntheticObservedEvent(
                event_id=f"syn_evt_{suffix}_{seq:02d}",
                journey_id=ctx.journey_id,
                merchant_id=ctx.merchant_id,
                order_id=ctx.order_id,
                payment_id=p_id,
                event_type=SyntheticEventType.PAYMENT_CREATED,
                occurred_at=_format_event_time(curr_t),
                emitted_at=_format_event_time(curr_t),
                sequence_number=seq,
                payload={
                    "order_id": ctx.order_id,
                    "payment_id": p_id,
                    "amount_in_cents": ctx.amount.amount_minor,
                    "currency": ctx.currency.value,
                    "payment_method": ctx.payment_method.value,
                    "status": "CREATED",
                    "attempt_number": att,
                    "instrument_ref": inst_ref,
                },
            )
        )
        seq += 1

        curr_t += timedelta(seconds=5)
        failure = PaymentFailure(
            category=FailureCategory.HARD_DECLINE,
            code=failure_code,
            reason=root_cause,
            is_retryable_hint=False,
            occurred_at=curr_t,
        )
        p.fail(failure, curr_t)

        events.append(
            SyntheticObservedEvent(
                event_id=f"syn_evt_{suffix}_{seq:02d}",
                journey_id=ctx.journey_id,
                merchant_id=ctx.merchant_id,
                order_id=ctx.order_id,
                payment_id=p_id,
                event_type=SyntheticEventType.PAYMENT_FAILED,
                occurred_at=_format_event_time(curr_t),
                emitted_at=_format_event_time(curr_t),
                sequence_number=seq,
                payload={
                    "order_id": ctx.order_id,
                    "payment_id": p_id,
                    "amount_in_cents": ctx.amount.amount_minor,
                    "currency": ctx.currency.value,
                    "status": "FAILED",
                    "attempt_number": att,
                    "error_code": failure_code,
                    "error_description": root_cause,
                },
            )
        )
        seq += 1
        attempt_truths.append(
            AttemptGroundTruth(
                payment_id=p_id,
                attempt_number=att,
                expected_final_state="FAILED",
                failure_category=failure_cat,
                failure_code=failure_code,
                root_cause=root_cause,
                is_retryable=False,
                recoverability=Recoverability.NON_RECOVERABLE,
            )
        )
        curr_t += timedelta(seconds=10)

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id=scenario_id,
        failure_category=failure_cat,
        failure_code=failure_code,
        root_cause=root_cause,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_recovery_strategy_class=strategy,
        expected_recovery_possible=False,
        expected_eventual_recovery=False,
        expected_final_payment_state="FAILED",
        expected_number_of_attempts=attempts,
        expected_recovered_amount_cents=0,
        currency=ctx.currency.value,
        is_revenue_at_risk=True,
        should_open_recovery_case=True,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=attempt_truths,
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=payment_ids,
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="FAILED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(curr_t),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S05: Network Timeout with Underlying Success (Transport Anomaly)
# -------------------------------------------------------------------------
def _gen_s05(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    # True state: captured at bank
    p = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=3)
    p.mark_authorized(t2)
    t3 = t2 + timedelta(seconds=2)
    p.capture(t3)
    order.mark_paid(t3)

    # Observed events: Client timed out at t3, but reconciliation at t4 confirmed capture
    t_client_timeout = t1 + timedelta(seconds=15)
    t_reconciled = t1 + timedelta(minutes=10)

    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_TIMED_OUT,
            occurred_at=_format_event_time(t_client_timeout),
            emitted_at=_format_event_time(t_client_timeout),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "TIMED_OUT",
                "attempt_number": 1,
                "error_code": "SYN_ERR_TIMEOUT",
                "error_description": "Client timed out waiting for gateway response",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t_reconciled),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 1,
            },
        ),
    ]

    att_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Captured at processor despite client-side timeout",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S05",
        failure_category=SyntheticFailureCategory.NETWORK_TIMEOUT,
        failure_code="SYN_ERR_CLIENT_TIMEOUT",
        root_cause="Client experienced timeout but processor settled payment successfully",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t_reconciled),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S07: 3DS Authentication Failure then customer completes on retry
# -------------------------------------------------------------------------
def _gen_s07(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        scenario_id="S07",
        failure_cat=SyntheticFailureCategory.AUTHENTICATION_FAILURE,
        failure_code="SYN_ERR_3DS_FAILED",
        root_cause_att1="3DS authentication failed or incorrect OTP entered",
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
    )


# -------------------------------------------------------------------------
# S13: Duplicate Retry on Already Paid Order
# -------------------------------------------------------------------------
def _gen_s13(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p1_id = f"{ctx.order_id}_p1"
    p2_id = f"{ctx.order_id}_p2"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    # Payment 1 captured
    p1 = Payment(
        id=PaymentId(p1_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=3)
    p1.mark_authorized(t2)
    t3 = t2 + timedelta(seconds=2)
    p1.capture(t3)
    order.mark_paid(t3)

    # Payment 2 attempted after order is already PAID -> rejected as duplicate
    t4 = t3 + timedelta(seconds=30)
    p2 = Payment(
        id=PaymentId(p2_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=2,
        created_at=t4,
        updated_at=t4,
    )
    t5 = t4 + timedelta(seconds=1)
    fail = PaymentFailure(
        category=FailureCategory.HARD_DECLINE,
        code="SYN_ERR_ORDER_ALREADY_PAID",
        reason="Order has already been paid",
        is_retryable_hint=False,
        occurred_at=t5,
    )
    p2.fail(fail, t5)

    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t3),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 1,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t4),
            emitted_at=_format_event_time(t4),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 2,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_05",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_FAILED,
            occurred_at=_format_event_time(t5),
            emitted_at=_format_event_time(t5),
            sequence_number=5,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "FAILED",
                "attempt_number": 2,
                "error_code": "SYN_ERR_ORDER_ALREADY_PAID",
                "error_description": "Order already settled in full",
            },
        ),
    ]

    att1_truth = AttemptGroundTruth(
        payment_id=p1_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Initial payment captured cleanly",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )
    att2_truth = AttemptGroundTruth(
        payment_id=p2_id,
        attempt_number=2,
        expected_final_state="FAILED",
        failure_category=SyntheticFailureCategory.DUPLICATE_ATTEMPT,
        failure_code="SYN_ERR_ORDER_ALREADY_PAID",
        root_cause="Duplicate payment attempt after order already paid",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S13",
        failure_category=SyntheticFailureCategory.DUPLICATE_ATTEMPT,
        failure_code="SYN_ERR_ORDER_ALREADY_PAID",
        root_cause="Duplicate payment submission rejected; initial payment remains settled",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=2,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att1_truth, att2_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p1_id, p2_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t5),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S16: Multiple Transient Failures (Different causes per attempt)
# -------------------------------------------------------------------------
def _gen_s16(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p1_id = f"{ctx.order_id}_p1"
    p2_id = f"{ctx.order_id}_p2"
    p3_id = f"{ctx.order_id}_p3"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    # Attempt 1: Issuer decline
    p1 = Payment(
        id=PaymentId(p1_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=4)
    p1.fail(
        PaymentFailure(
            category=FailureCategory.SOFT_DECLINE,
            code="SYN_ERR_SOFT_DECLINE",
            reason="Issuer temporary decline",
            is_retryable_hint=True,
            occurred_at=t2,
        ),
        t2,
    )

    # Attempt 2: Network timeout
    t3 = t2 + timedelta(seconds=20)
    p2 = Payment(
        id=PaymentId(p2_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=2,
        created_at=t3,
        updated_at=t3,
    )
    t4 = t3 + timedelta(seconds=15)
    p2.fail(
        PaymentFailure(
            category=FailureCategory.TIMEOUT,
            code="SYN_ERR_NETWORK_TIMEOUT",
            reason="Issuer response timeout",
            is_retryable_hint=True,
            occurred_at=t4,
        ),
        t4,
    )

    # Attempt 3: Retried and captured
    t5 = t4 + timedelta(seconds=30)
    p3 = Payment(
        id=PaymentId(p3_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=3,
        created_at=t5,
        updated_at=t5,
    )
    t6 = t5 + timedelta(seconds=3)
    p3.mark_authorized(t6)
    t7 = t6 + timedelta(seconds=2)
    p3.capture(t7)
    order.mark_paid(t7)

    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p1_id,
            event_type=SyntheticEventType.PAYMENT_FAILED,
            occurred_at=_format_event_time(t2),
            emitted_at=_format_event_time(t2),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p1_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "FAILED",
                "attempt_number": 1,
                "error_code": "SYN_ERR_SOFT_DECLINE",
                "error_description": "Issuer temporary decline",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t3),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 2,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_05",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p2_id,
            event_type=SyntheticEventType.PAYMENT_FAILED,
            occurred_at=_format_event_time(t4),
            emitted_at=_format_event_time(t4),
            sequence_number=5,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p2_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "FAILED",
                "attempt_number": 2,
                "error_code": "SYN_ERR_NETWORK_TIMEOUT",
                "error_description": "Issuer response timeout",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_06",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p3_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t5),
            emitted_at=_format_event_time(t5),
            sequence_number=6,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p3_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 3,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_07",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p3_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t7),
            emitted_at=_format_event_time(t7),
            sequence_number=7,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p3_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 3,
            },
        ),
    ]

    att1_truth = AttemptGroundTruth(
        payment_id=p1_id,
        attempt_number=1,
        expected_final_state="FAILED",
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        failure_code="SYN_ERR_SOFT_DECLINE",
        root_cause="Issuer temporary decline",
        is_retryable=True,
        recoverability=Recoverability.RECOVERABLE,
    )
    att2_truth = AttemptGroundTruth(
        payment_id=p2_id,
        attempt_number=2,
        expected_final_state="FAILED",
        failure_category=SyntheticFailureCategory.NETWORK_TIMEOUT,
        failure_code="SYN_ERR_NETWORK_TIMEOUT",
        root_cause="Issuer response timeout",
        is_retryable=True,
        recoverability=Recoverability.RECOVERABLE,
    )
    att3_truth = AttemptGroundTruth(
        payment_id=p3_id,
        attempt_number=3,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Attempt 3 captured cleanly",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S16",
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        failure_code="SYN_ERR_SOFT_DECLINE",
        root_cause="Multiple transient failures before eventual successful capture",
        recoverability=Recoverability.RECOVERABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.RETRY_SAME_METHOD,
        expected_recovery_possible=True,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=3,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=True,
        should_open_recovery_case=True,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att1_truth, att2_truth, att3_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p1_id, p2_id, p3_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t7),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S17: Late Asynchronous Success (Transport Anomaly)
# -------------------------------------------------------------------------
def _gen_s17(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    p = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=20)
    p.mark_pending(t2)
    t3 = t2 + timedelta(seconds=10)
    p.capture(t3)
    order.mark_paid(t3)

    # Transport delay: Event 4 (CAPTURED) emitted 6 hours later!
    t_delayed_emit = t3 + timedelta(hours=6)

    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_PENDING,
            occurred_at=_format_event_time(t2),
            emitted_at=_format_event_time(t2),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "PENDING",
                "attempt_number": 1,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_04",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t_delayed_emit),
            sequence_number=4,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 1,
            },
        ),
    ]

    att_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Late webhook notification arrived after banking settlement",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S17",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Asynchronous capture webhook delayed in transport",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t_delayed_emit),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S18: Out-of-Order Delivery (Transport Anomaly)
# -------------------------------------------------------------------------
def _gen_s18(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    p = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=3)
    p.mark_authorized(t2)
    t3 = t2 + timedelta(seconds=2)
    p.capture(t3)
    order.mark_paid(t3)

    # Transport noise: PAYMENT_CAPTURED emitted at t4, PAYMENT_AUTHORIZED emitted at t5 (out-of-order)
    t4 = t3 + timedelta(seconds=1)
    t5 = t4 + timedelta(seconds=2)

    evt_order = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_01",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=None,
        event_type=SyntheticEventType.ORDER_CREATED,
        occurred_at=_format_event_time(t0),
        emitted_at=_format_event_time(t0),
        sequence_number=1,
        payload={
            "order_id": ctx.order_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "CREATED",
        },
    )
    evt_pcreated = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_02",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_CREATED,
        occurred_at=_format_event_time(t1),
        emitted_at=_format_event_time(t1),
        sequence_number=2,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "payment_method": ctx.payment_method.value,
            "status": "CREATED",
            "attempt_number": 1,
            "instrument_ref": inst_ref,
        },
    )
    evt_captured = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_03",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_CAPTURED,
        occurred_at=_format_event_time(t3),
        emitted_at=_format_event_time(t4),
        sequence_number=3,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "CAPTURED",
            "attempt_number": 1,
        },
    )
    evt_authorized = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_04",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_AUTHORIZED,
        occurred_at=_format_event_time(t2),
        emitted_at=_format_event_time(t5),
        sequence_number=4,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "AUTHORIZED",
            "attempt_number": 1,
        },
    )

    events = [evt_order, evt_pcreated, evt_captured, evt_authorized]

    att_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Captured cleanly; webhooks arrived out of order",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S18",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Out-of-order event delivery; true economic lifecycle captured",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t5),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S19: Duplicate Event Delivery (Transport Anomaly)
# -------------------------------------------------------------------------
def _gen_s19(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    p = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=4)
    p.fail(
        PaymentFailure(
            category=FailureCategory.SOFT_DECLINE,
            code="SYN_ERR_SOFT_DECLINE",
            reason="Issuer transient decline",
            is_retryable_hint=True,
            occurred_at=t2,
        ),
        t2,
    )

    evt1 = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_01",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=None,
        event_type=SyntheticEventType.ORDER_CREATED,
        occurred_at=_format_event_time(t0),
        emitted_at=_format_event_time(t0),
        sequence_number=1,
        payload={
            "order_id": ctx.order_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "CREATED",
        },
    )
    evt2 = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_02",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_CREATED,
        occurred_at=_format_event_time(t1),
        emitted_at=_format_event_time(t1),
        sequence_number=2,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "payment_method": ctx.payment_method.value,
            "status": "CREATED",
            "attempt_number": 1,
            "instrument_ref": inst_ref,
        },
    )
    evt3 = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_03",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_FAILED,
        occurred_at=_format_event_time(t2),
        emitted_at=_format_event_time(t2),
        sequence_number=3,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "FAILED",
            "attempt_number": 1,
            "error_code": "SYN_ERR_SOFT_DECLINE",
            "error_description": "Issuer transient decline",
        },
    )
    # Duplicate delivery: identical event ID and payload delivered at t2 + 5 seconds
    evt3_dup = SyntheticObservedEvent(
        event_id=f"syn_evt_{suffix}_03",
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        order_id=ctx.order_id,
        payment_id=p_id,
        event_type=SyntheticEventType.PAYMENT_FAILED,
        occurred_at=_format_event_time(t2),
        emitted_at=_format_event_time(t2 + timedelta(seconds=5)),
        sequence_number=4,
        payload={
            "order_id": ctx.order_id,
            "payment_id": p_id,
            "amount_in_cents": ctx.amount.amount_minor,
            "currency": ctx.currency.value,
            "status": "FAILED",
            "attempt_number": 1,
            "error_code": "SYN_ERR_SOFT_DECLINE",
            "error_description": "Issuer transient decline",
        },
    )

    events = [evt1, evt2, evt3, evt3_dup]

    att_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="FAILED",
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        failure_code="SYN_ERR_SOFT_DECLINE",
        root_cause="Issuer transient decline; webhook delivered twice",
        is_retryable=True,
        recoverability=Recoverability.RECOVERABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S19",
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        failure_code="SYN_ERR_SOFT_DECLINE",
        root_cause="Duplicate event delivery for failed attempt",
        recoverability=Recoverability.RECOVERABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.RETRY_SAME_METHOD,
        expected_recovery_possible=True,
        expected_eventual_recovery=False,
        expected_final_payment_state="FAILED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=0,
        currency=ctx.currency.value,
        is_revenue_at_risk=True,
        should_open_recovery_case=True,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="FAILED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t2 + timedelta(seconds=5)),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S20: Missing Intermediate Event (Transport Anomaly)
# -------------------------------------------------------------------------
def _gen_s20(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    suffix = ctx.journey_id[-6:]
    inst_ref = _make_instrument_ref(ctx.payment_method, suffix)
    p_id = f"{ctx.order_id}_p1"

    t0 = ctx.anchor_time
    order = Order(
        id=OrderId(ctx.order_id),
        merchant_id=MerchantId(ctx.merchant_id),
        amount=ctx.amount,
        status=OrderStatus.CREATED,
        created_at=t0,
        updated_at=t0,
    )
    t1 = t0 + timedelta(seconds=2)
    order.mark_open(t1)

    p = Payment(
        id=PaymentId(p_id),
        merchant_id=MerchantId(ctx.merchant_id),
        order_id=OrderId(ctx.order_id),
        amount=ctx.amount,
        state=PaymentState.CREATED,
        attempt_number=1,
        created_at=t1,
        updated_at=t1,
    )
    t2 = t1 + timedelta(seconds=3)
    p.mark_authorized(t2)
    t3 = t2 + timedelta(seconds=2)
    p.capture(t3)
    order.mark_paid(t3)

    # Missing event: PAYMENT_AUTHORIZED is completely dropped in network
    events = [
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_01",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=None,
            event_type=SyntheticEventType.ORDER_CREATED,
            occurred_at=_format_event_time(t0),
            emitted_at=_format_event_time(t0),
            sequence_number=1,
            payload={
                "order_id": ctx.order_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CREATED",
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_02",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CREATED,
            occurred_at=_format_event_time(t1),
            emitted_at=_format_event_time(t1),
            sequence_number=2,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "payment_method": ctx.payment_method.value,
                "status": "CREATED",
                "attempt_number": 1,
                "instrument_ref": inst_ref,
            },
        ),
        SyntheticObservedEvent(
            event_id=f"syn_evt_{suffix}_03",
            journey_id=ctx.journey_id,
            merchant_id=ctx.merchant_id,
            order_id=ctx.order_id,
            payment_id=p_id,
            event_type=SyntheticEventType.PAYMENT_CAPTURED,
            occurred_at=_format_event_time(t3),
            emitted_at=_format_event_time(t3),
            sequence_number=3,
            payload={
                "order_id": ctx.order_id,
                "payment_id": p_id,
                "amount_in_cents": ctx.amount.amount_minor,
                "currency": ctx.currency.value,
                "status": "CAPTURED",
                "attempt_number": 1,
            },
        ),
    ]

    att_truth = AttemptGroundTruth(
        payment_id=p_id,
        attempt_number=1,
        expected_final_state="CAPTURED",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Captured cleanly; authorized event lost in transit",
        is_retryable=False,
        recoverability=Recoverability.NOT_APPLICABLE,
    )

    gt = GroundTruth(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        scenario_id="S20",
        failure_category=SyntheticFailureCategory.NONE,
        failure_code=None,
        root_cause="Missing intermediate event; true economic lifecycle captured",
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_recovery_strategy_class=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        expected_recovery_possible=False,
        expected_eventual_recovery=True,
        expected_final_payment_state="CAPTURED",
        expected_number_of_attempts=1,
        expected_recovered_amount_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        is_revenue_at_risk=False,
        should_open_recovery_case=False,
        synthetic_labels_version=ctx.labels_version,
        attempt_truths=[att_truth],
    )

    journey = SyntheticPaymentJourney(
        journey_id=ctx.journey_id,
        merchant_id=ctx.merchant_id,
        synthetic_customer_id=ctx.synthetic_customer_id,
        order_id=ctx.order_id,
        payment_ids=[p_id],
        amount_in_cents=ctx.amount.amount_minor,
        currency=ctx.currency.value,
        payment_method=ctx.payment_method,
        last_observed_state="CAPTURED",
        observed_event_ids=[e.event_id for e in events],
        generated_at=_format_event_time(t3),
    )

    return journey, events, gt


# -------------------------------------------------------------------------
# S21: UPI Collect Request Expired (Recovered on 2nd attempt)
# -------------------------------------------------------------------------
def _gen_s21(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        scenario_id="S21",
        failure_cat=SyntheticFailureCategory.NETWORK_TIMEOUT,
        failure_code="SYN_ERR_COLLECT_EXPIRED",
        root_cause_att1="UPI collect request expired before payer approval",
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
    )


# -------------------------------------------------------------------------
# Scenario Builders for Remaining Scenarios
# -------------------------------------------------------------------------
def _gen_s02(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S02",
        SyntheticFailureCategory.ISSUER_DECLINE,
        "SYN_ERR_SOFT_DECLINE",
        "Temporary issuer bank decline",
        Recoverability.RECOVERABLE,
        RecoveryStrategyClass.RETRY_SAME_METHOD,
    )


def _gen_s03(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S03",
        SyntheticFailureCategory.INSUFFICIENT_FUNDS,
        "SYN_ERR_INSUFFICIENT_FUNDS",
        "Insufficient balance; payer added funds and retried",
        Recoverability.CONDITIONALLY_RECOVERABLE,
        RecoveryStrategyClass.WAIT_AND_RETRY,
    )


def _gen_s04(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S04",
        SyntheticFailureCategory.INSUFFICIENT_FUNDS,
        "SYN_ERR_INSUFFICIENT_FUNDS",
        "Persistent balance deficit within evaluation horizon",
        RecoveryStrategyClass.DO_NOT_RETRY,
        attempts=2,
    )


def _gen_s06(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S06",
        SyntheticFailureCategory.NETWORK_TIMEOUT,
        "SYN_ERR_TIMEOUT",
        "Network timeout before reaching processor; retry captured",
        Recoverability.RECOVERABLE,
        RecoveryStrategyClass.RETRY_SAME_METHOD,
    )


def _gen_s08(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S08",
        SyntheticFailureCategory.AUTHENTICATION_FAILURE,
        "SYN_ERR_3DS_ABANDONED",
        "Payer permanently abandoned 3DS authentication challenge",
        RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        attempts=1,
    )


def _gen_s09(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S09",
        SyntheticFailureCategory.EXPIRED_INSTRUMENT,
        "SYN_ERR_CARD_EXPIRED",
        "Card validity period expired; instrument invalid",
        RecoveryStrategyClass.USE_ALTERNATE_METHOD,
        attempts=1,
    )


def _gen_s10(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S10",
        SyntheticFailureCategory.INVALID_INSTRUMENT,
        "SYN_ERR_INVALID_DETAILS",
        "Invalid card number or non-existent UPI handle",
        RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        attempts=1,
    )


def _gen_s11(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S11",
        SyntheticFailureCategory.GATEWAY_UNAVAILABLE,
        "SYN_ERR_GATEWAY_503",
        "Gateway service unavailable HTTP 503; retried after recovery",
        Recoverability.RECOVERABLE,
        RecoveryStrategyClass.WAIT_AND_RETRY,
    )


def _gen_s12(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S12",
        SyntheticFailureCategory.PROCESSING_ERROR,
        "SYN_ERR_PROCESSOR_EXCEPTION",
        "Processor transient internal error; retried and captured",
        Recoverability.RECOVERABLE,
        RecoveryStrategyClass.RETRY_SAME_METHOD,
    )


def _gen_s14(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S14",
        SyntheticFailureCategory.FRAUD_OR_RISK_DECLINE,
        "SYN_ERR_RISK_BLOCK",
        "Transaction blocked by risk and velocity rules",
        RecoveryStrategyClass.DO_NOT_RETRY,
        attempts=1,
    )


def _gen_s15(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_two_attempt_retry_success(
        ctx,
        "S15",
        SyntheticFailureCategory.CUSTOMER_ABANDONMENT,
        "SYN_ERR_CHECKOUT_TIMEOUT",
        "Customer closed tab; later returned and completed checkout",
        Recoverability.CONDITIONALLY_RECOVERABLE,
        RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
    )


def _gen_s22(
    ctx: ScenarioContext,
) -> tuple[SyntheticPaymentJourney, list[SyntheticObservedEvent], GroundTruth]:
    return _gen_permanent_failure(
        ctx,
        "S22",
        SyntheticFailureCategory.PROVIDER_CONFIGURATION,
        "SYN_ERR_INVALID_MERCHANT_KEY",
        "Merchant credentials misconfigured or MID blocked",
        RecoveryStrategyClass.DO_NOT_RETRY,
        attempts=1,
    )


# -------------------------------------------------------------------------
# Versioned Catalog Registry
# -------------------------------------------------------------------------
SCENARIO_CATALOG: dict[str, ScenarioDefinition] = {
    "S01": ScenarioDefinition(
        scenario_id="S01",
        name="Immediate Success",
        description="Single attempt cleanly authorized and captured",
        allowed_methods=ALL_METHODS,
        failure_category=SyntheticFailureCategory.NONE,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=4000,
        is_transport_anomaly=False,
        generator_fn=_gen_s01,
    ),
    "S02": ScenarioDefinition(
        scenario_id="S02",
        name="Temporary Issuer Decline",
        description="Attempt 1 soft decline; retry attempt 2 succeeds",
        allowed_methods=CARD_AND_NETBANKING,
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.RETRY_SAME_METHOD,
        default_weight_bps=800,
        is_transport_anomaly=False,
        generator_fn=_gen_s02,
    ),
    "S03": ScenarioDefinition(
        scenario_id="S03",
        name="Insufficient Funds (Recovered)",
        description="Attempt 1 failed; payer adds funds; retry succeeds",
        allowed_methods=CARDS_UPI_WALLET,
        failure_category=SyntheticFailureCategory.INSUFFICIENT_FUNDS,
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.WAIT_AND_RETRY,
        default_weight_bps=500,
        is_transport_anomaly=False,
        generator_fn=_gen_s03,
    ),
    "S04": ScenarioDefinition(
        scenario_id="S04",
        name="Insufficient Funds (Permanent)",
        description="Attempt 1 & 2 fail due to balance; remains failed within horizon",
        allowed_methods=CARDS_UPI_WALLET,
        failure_category=SyntheticFailureCategory.INSUFFICIENT_FUNDS,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.DO_NOT_RETRY,
        default_weight_bps=400,
        is_transport_anomaly=False,
        generator_fn=_gen_s04,
    ),
    "S05": ScenarioDefinition(
        scenario_id="S05",
        name="Network Timeout (Underlying Success)",
        description="Merchant times out, but PSP captured payment; confirmed via reconciliation",
        allowed_methods=NON_EMI_METHODS,
        failure_category=SyntheticFailureCategory.NETWORK_TIMEOUT,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=300,
        is_transport_anomaly=True,
        generator_fn=_gen_s05,
    ),
    "S06": ScenarioDefinition(
        scenario_id="S06",
        name="Network Timeout (Retry Success)",
        description="Timeout before bank; retry attempt 2 succeeds",
        allowed_methods=NON_EMI_METHODS,
        failure_category=SyntheticFailureCategory.NETWORK_TIMEOUT,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.RETRY_SAME_METHOD,
        default_weight_bps=400,
        is_transport_anomaly=False,
        generator_fn=_gen_s06,
    ),
    "S07": ScenarioDefinition(
        scenario_id="S07",
        name="Auth Failure (Payer Resolves)",
        description="3DS auth fails; payer re-authenticates and succeeds",
        allowed_methods=CARD_AND_NETBANKING,
        failure_category=SyntheticFailureCategory.AUTHENTICATION_FAILURE,
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        default_weight_bps=400,
        is_transport_anomaly=False,
        generator_fn=_gen_s07,
    ),
    "S08": ScenarioDefinition(
        scenario_id="S08",
        name="Auth Abandonment (Permanent)",
        description="Payer abandons 3DS authentication challenge permanently",
        allowed_methods=CARD_AND_NETBANKING,
        failure_category=SyntheticFailureCategory.AUTHENTICATION_FAILURE,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        default_weight_bps=300,
        is_transport_anomaly=False,
        generator_fn=_gen_s08,
    ),
    "S09": ScenarioDefinition(
        scenario_id="S09",
        name="Expired Card Instrument",
        description="Card validity date has expired; permanent decline",
        allowed_methods=CARD_ONLY,
        failure_category=SyntheticFailureCategory.EXPIRED_INSTRUMENT,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.USE_ALTERNATE_METHOD,
        default_weight_bps=250,
        is_transport_anomaly=False,
        generator_fn=_gen_s09,
    ),
    "S10": ScenarioDefinition(
        scenario_id="S10",
        name="Invalid Instrument Details",
        description="Non-existent VPA or invalid card format",
        allowed_methods=CARD_AND_UPI,
        failure_category=SyntheticFailureCategory.INVALID_INSTRUMENT,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        default_weight_bps=250,
        is_transport_anomaly=False,
        generator_fn=_gen_s10,
    ),
    "S11": ScenarioDefinition(
        scenario_id="S11",
        name="Gateway Outage / 503",
        description="Gateway returns 503; retry succeeds after recovery",
        allowed_methods=ALL_METHODS,
        failure_category=SyntheticFailureCategory.GATEWAY_UNAVAILABLE,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.WAIT_AND_RETRY,
        default_weight_bps=300,
        is_transport_anomaly=False,
        generator_fn=_gen_s11,
    ),
    "S12": ScenarioDefinition(
        scenario_id="S12",
        name="Provider Processing Error",
        description="Transient PSP glitch; retry attempt 2 succeeds",
        allowed_methods=NON_EMI_METHODS,
        failure_category=SyntheticFailureCategory.PROCESSING_ERROR,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.RETRY_SAME_METHOD,
        default_weight_bps=300,
        is_transport_anomaly=False,
        generator_fn=_gen_s12,
    ),
    "S13": ScenarioDefinition(
        scenario_id="S13",
        name="Duplicate Attempt on Paid Order",
        description="Order already paid; duplicate attempt rejected",
        allowed_methods=NON_EMI_METHODS,
        failure_category=SyntheticFailureCategory.DUPLICATE_ATTEMPT,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=200,
        is_transport_anomaly=False,
        generator_fn=_gen_s13,
    ),
    "S14": ScenarioDefinition(
        scenario_id="S14",
        name="Fraud / Risk Rule Decline",
        description="Blocked by risk rules / velocity check; hard decline",
        allowed_methods=CARD_AND_UPI,
        failure_category=SyntheticFailureCategory.FRAUD_OR_RISK_DECLINE,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.DO_NOT_RETRY,
        default_weight_bps=200,
        is_transport_anomaly=False,
        generator_fn=_gen_s14,
    ),
    "S15": ScenarioDefinition(
        scenario_id="S15",
        name="Customer Abandonment at Checkout",
        description="Payer closes checkout window; later returns and settles order",
        allowed_methods=CARDS_UPI_WALLET,
        failure_category=SyntheticFailureCategory.CUSTOMER_ABANDONMENT,
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        default_weight_bps=300,
        is_transport_anomaly=False,
        generator_fn=_gen_s15,
    ),
    "S16": ScenarioDefinition(
        scenario_id="S16",
        name="Multiple Transient Failures",
        description="Attempt 1 issuer decline, attempt 2 timeout, attempt 3 succeeds",
        allowed_methods=CARD_AND_NETBANKING,
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.RETRY_SAME_METHOD,
        default_weight_bps=250,
        is_transport_anomaly=False,
        generator_fn=_gen_s16,
    ),
    "S17": ScenarioDefinition(
        scenario_id="S17",
        name="Late Asynchronous Success",
        description="Webhook arrives hours later; captured asynchronously",
        allowed_methods=frozenset({PaymentMethod.UPI, PaymentMethod.NETBANKING}),
        failure_category=SyntheticFailureCategory.NONE,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=200,
        is_transport_anomaly=True,
        generator_fn=_gen_s17,
    ),
    "S18": ScenarioDefinition(
        scenario_id="S18",
        name="Out-of-Order Delivery",
        description="PAYMENT_CAPTURED emitted before PAYMENT_AUTHORIZED",
        allowed_methods=CARD_AND_UPI,
        failure_category=SyntheticFailureCategory.NONE,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=200,
        is_transport_anomaly=True,
        generator_fn=_gen_s18,
    ),
    "S19": ScenarioDefinition(
        scenario_id="S19",
        name="Duplicate Event Delivery",
        description="Same PAYMENT_FAILED webhook delivered twice",
        allowed_methods=CARD_AND_UPI,
        failure_category=SyntheticFailureCategory.ISSUER_DECLINE,
        recoverability=Recoverability.RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.RETRY_SAME_METHOD,
        default_weight_bps=200,
        is_transport_anomaly=True,
        generator_fn=_gen_s19,
    ),
    "S20": ScenarioDefinition(
        scenario_id="S20",
        name="Missing Intermediate Event",
        description="PAYMENT_AUTHORIZED lost in transit; capture delivered",
        allowed_methods=CARD_AND_NETBANKING,
        failure_category=SyntheticFailureCategory.NONE,
        recoverability=Recoverability.NOT_APPLICABLE,
        expected_strategy=RecoveryStrategyClass.NO_RECOVERY_NEEDED,
        default_weight_bps=200,
        is_transport_anomaly=True,
        generator_fn=_gen_s20,
    ),
    "S21": ScenarioDefinition(
        scenario_id="S21",
        name="UPI Collect Expired (Recovered)",
        description="Payer misses collect notification; 2nd collect succeeds",
        allowed_methods=UPI_ONLY,
        failure_category=SyntheticFailureCategory.NETWORK_TIMEOUT,
        recoverability=Recoverability.CONDITIONALLY_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.CUSTOMER_ACTION_REQUIRED,
        default_weight_bps=150,
        is_transport_anomaly=False,
        generator_fn=_gen_s21,
    ),
    "S22": ScenarioDefinition(
        scenario_id="S22",
        name="Provider Configuration Error",
        description="Invalid merchant keys / merchant account suspended",
        allowed_methods=ALL_METHODS,
        failure_category=SyntheticFailureCategory.PROVIDER_CONFIGURATION,
        recoverability=Recoverability.NON_RECOVERABLE,
        expected_strategy=RecoveryStrategyClass.DO_NOT_RETRY,
        default_weight_bps=100,
        is_transport_anomaly=False,
        generator_fn=_gen_s22,
    ),
}
