"""Bi-directional mapper for Order domain aggregate and OrderModel."""

from datetime import UTC

from app.application.exceptions import DataCorruptionError
from app.domain.entities.order import Order, OrderStatus
from app.domain.types import MerchantId, OrderId
from app.domain.values.currency import Currency
from app.domain.values.money import Money
from app.infrastructure.persistence.models.order import OrderModel


class OrderMapper:
    """Explicit mapping between Order domain aggregate and OrderModel ORM entity."""

    @staticmethod
    def to_domain(model: OrderModel) -> Order:
        """Map ORM OrderModel to pure Order domain aggregate."""
        try:
            created_at = model.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)

            updated_at = model.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)

            currency = Currency.from_str(model.currency)
            money = Money.from_minor(model.amount_minor, currency)
            status = OrderStatus(model.status)

            return Order(
                id=OrderId(model.id),
                merchant_id=MerchantId(model.merchant_id),
                amount=money,
                status=status,
                created_at=created_at,
                updated_at=updated_at,
                external_reference=model.external_reference,
            )
        except Exception as exc:
            raise DataCorruptionError("Order", model.id, str(exc)) from exc

    @staticmethod
    def to_model(domain: Order, version: int = 1) -> OrderModel:
        """Map pure Order domain aggregate to ORM OrderModel."""
        return OrderModel(
            id=str(domain.id),
            merchant_id=str(domain.merchant_id),
            amount_minor=domain.amount.amount_minor,
            currency=domain.amount.currency.value,
            status=domain.status.value,
            external_reference=domain.external_reference,
            created_at=domain.created_at,
            updated_at=domain.updated_at,
            version=version,
        )
