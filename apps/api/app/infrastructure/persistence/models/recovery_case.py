"""SQLAlchemy model for recovery cases."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class RecoveryCaseModel(Base):
    """Persisted revenue-loss recovery case aggregate."""

    __tablename__ = "recovery_cases"
    __table_args__ = (
        CheckConstraint("amount_at_risk_minor > 0", name="ck_recovery_cases_amount_positive"),
        CheckConstraint("length(currency) = 3", name="ck_recovery_cases_currency_iso3"),
        CheckConstraint("attempt_count >= 0", name="ck_recovery_cases_attempt_non_negative"),
        Index("ix_recovery_cases_merchant_state", "merchant_id", "state"),
        Index("ix_recovery_cases_merchant_opened_at", "merchant_id", "opened_at"),
        # Partial unique index: only ONE active case per payment
        Index(
            "uq_active_recovery_case_per_payment",
            "payment_id",
            unique=True,
            postgresql_where="state NOT IN ('VERIFIED_RECOVERED', 'EXHAUSTED', 'CANCELLED')",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount_at_risk_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Failure context snapshot
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    failure_is_retryable_hint: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    failure_occurred_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
