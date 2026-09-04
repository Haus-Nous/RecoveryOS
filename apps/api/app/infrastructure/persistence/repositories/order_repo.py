"""SQLAlchemy implementation of OrderRepository."""

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ConcurrencyConflictError
from app.application.ports.repositories import OrderRepository
from app.domain.entities.order import Order
from app.domain.types import MerchantId, OrderId
from app.infrastructure.persistence.mappers.order_mapper import OrderMapper
from app.infrastructure.persistence.models.order import OrderModel


class SqlAlchemyOrderRepository(OrderRepository):
    """PostgreSQL repository for Order aggregates with tenant scoping and optimistic locking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, merchant_id: MerchantId, order_id: OrderId) -> Order | None:
        stmt = select(OrderModel).where(
            OrderModel.id == str(order_id),
            OrderModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrderMapper.to_domain(model) if model is not None else None

    async def save(
        self,
        merchant_id: MerchantId,
        order: Order,
        expected_version: int | None = None,
    ) -> Order:
        # Check if record exists
        stmt = select(OrderModel).where(
            OrderModel.id == str(order.id),
            OrderModel.merchant_id == str(merchant_id),
        )
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is None:
            # Insert
            new_model = OrderMapper.to_model(order, version=1)
            self._session.add(new_model)
            await self._session.flush()
            return order

        # Update with optimistic concurrency check
        if expected_version is not None and existing.version != expected_version:
            raise ConcurrencyConflictError(
                entity_type="Order",
                entity_id=str(order.id),
                expected_version=expected_version,
                actual_version=existing.version,
            )

        new_version = existing.version + 1
        update_stmt = (
            update(OrderModel)
            .where(
                OrderModel.id == str(order.id),
                OrderModel.merchant_id == str(merchant_id),
                OrderModel.version == existing.version,
            )
            .values(
                amount_minor=order.amount.amount_minor,
                currency=order.amount.currency.value,
                status=order.status.value,
                external_reference=order.external_reference,
                updated_at=order.updated_at,
                version=new_version,
            )
        )
        res = await self._session.execute(update_stmt)
        cursor_res = cast(CursorResult[Any], res)
        if cursor_res.rowcount == 0:
            raise ConcurrencyConflictError(
                entity_type="Order",
                entity_id=str(order.id),
                expected_version=existing.version,
            )

        await self._session.flush()
        return order
