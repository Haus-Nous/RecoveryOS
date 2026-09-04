"""SQLAlchemy model for commercial orders."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class OrderModel(Base):
    """Persisted commercial checkout order."""

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_orders_amount_positive"),
        CheckConstraint("length(currency) = 3", name="ck_orders_currency_iso3"),
        UniqueConstraint("id", "merchant_id", name="uq_orders_id_merchant"),
        Index("ix_orders_merchant_status", "merchant_id", "status"),
        Index("ix_orders_merchant_created_at", "merchant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
