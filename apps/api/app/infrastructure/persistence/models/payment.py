"""SQLAlchemy model for payment attempts."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class PaymentModel(Base):
    """Persisted payment attempt aggregate."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_payments_amount_positive"),
        CheckConstraint("length(currency) = 3", name="ck_payments_currency_iso3"),
        CheckConstraint("attempt_number >= 1", name="ck_payments_attempt_positive"),
        UniqueConstraint("id", "merchant_id", name="uq_payments_id_merchant"),
        ForeignKeyConstraint(
            ["order_id", "merchant_id"],
            ["orders.id", "orders.merchant_id"],
            name="fk_payments_order_merchant",
            ondelete="RESTRICT",
        ),
        Index("ix_payments_merchant_order", "merchant_id", "order_id"),
        Index("ix_payments_merchant_state", "merchant_id", "state"),
        Index("ix_payments_merchant_created_at", "merchant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Structured failure context fields (flattened value object)
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    failure_is_retryable_hint: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
