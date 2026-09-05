"""Safe database seeder for persisting synthetic domain aggregates via UnitOfWork."""

from collections.abc import Sequence
from datetime import UTC, datetime

from app.application.ports.unit_of_work import UnitOfWork
from app.core.config import get_settings
from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.payment import Payment, PaymentState
from app.domain.types import MerchantId, OrderId, PaymentId
from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.infrastructure.persistence.models.merchant import MerchantModel
from app.lab.generator import SyntheticMerchant
from app.lab.models import GroundTruth, SyntheticPaymentJourney


def assert_safe_environment() -> None:
    """Fail-closed assertion ensuring database seeding is never run in production or staging."""
    settings = get_settings()
    env = settings.app_env.lower()
    if env in ("production", "staging", "prod", "stage"):
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: Synthetic database persistence is strictly "
            f"prohibited in '{env}' environment!"
        )


async def seed_synthetic_merchants(
    uow: UnitOfWork,
    merchants: Sequence[SyntheticMerchant],
) -> None:
    """Ensure synthetic merchants exist via UnitOfWork."""
    assert_safe_environment()
    now = datetime.now(UTC)
    for m in merchants:
        existing = await uow.memberships.get_merchant_by_id(MerchantId(m.merchant_id))
        if not existing:
            m_model = MerchantModel(
                id=m.merchant_id,
                name=m.name,
                slug=m.slug,
                created_at=now,
                updated_at=now,
            )
            await uow.memberships.create_merchant(m_model)


async def persist_synthetic_batch(
    uow: UnitOfWork,
    records: Sequence[tuple[SyntheticPaymentJourney, GroundTruth]],
) -> int:
    """Persist synthetic Orders and Payments to the database via repository ports.

    CRITICAL INVARIANTS:
    1. Only domain aggregates (Order, Payment) are persisted.
    2. Synthetic observed events are NEVER written to domain_events or outbox_messages.
    3. Every entity is explicitly tenant-scoped.
    """
    assert_safe_environment()
    persisted_count = 0

    for journey, gt in records:
        merchant_id = MerchantId(journey.merchant_id)
        order_id = OrderId(journey.order_id)
        currency = Currency.from_str(journey.currency)
        amount = Money.from_minor(journey.amount_in_cents, currency)
        created_at = datetime.fromisoformat(journey.generated_at)

        # Determine true final order status based on ground truth
        final_order_status = (
            OrderStatus.PAID if gt.expected_final_payment_state == "CAPTURED" else OrderStatus.OPEN
        )

        order = Order(
            id=order_id,
            merchant_id=merchant_id,
            amount=amount,
            status=final_order_status,
            created_at=created_at,
            updated_at=created_at,
        )
        await uow.orders.save(merchant_id, order)

        # Save payment attempts
        for att in gt.attempt_truths:
            p_id = PaymentId(att.payment_id)
            state = (
                PaymentState.CAPTURED
                if att.expected_final_state == "CAPTURED"
                else PaymentState.FAILED
            )
            payment = Payment(
                id=p_id,
                merchant_id=merchant_id,
                order_id=order_id,
                amount=amount,
                state=state,
                attempt_number=att.attempt_number,
                created_at=created_at,
                updated_at=created_at,
            )
            await uow.payments.save(merchant_id, payment)

        persisted_count += 1

    return persisted_count
