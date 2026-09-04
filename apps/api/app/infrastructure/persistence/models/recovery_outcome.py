"""SQLAlchemy model for recovery outcomes."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class RecoveryOutcomeModel(Base):
    """Persisted recovery outcome and verification state.

    INVARIANT:
    1. One outcome per recovery action (unique constraint).
    2. VERIFIED status strictly requires verification_reference, verified_at,
       and RECOVERY_OBSERVED status.
    """

    __tablename__ = "recovery_outcomes"
    __table_args__ = (
        CheckConstraint(
            "amount_recovered_minor >= 0", name="ck_recovery_outcomes_amount_non_negative"
        ),
        CheckConstraint("length(currency) = 3", name="ck_recovery_outcomes_currency_iso3"),
        # DB-level invariant check: VERIFIED requires evidence, timestamp, and RECOVERY_OBSERVED
        CheckConstraint(
            "(verification_status != 'VERIFIED') OR "
            "(verification_reference IS NOT NULL "
            "AND verified_at IS NOT NULL "
            "AND status = 'RECOVERY_OBSERVED')",
            name="ck_recovery_outcomes_verified_requires_evidence",
        ),
        ForeignKeyConstraint(
            ["recovery_case_id", "merchant_id"],
            ["recovery_cases.id", "recovery_cases.merchant_id"],
            name="fk_recovery_outcomes_case_merchant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["recovery_action_id", "merchant_id"],
            ["recovery_actions.id", "recovery_actions.merchant_id"],
            name="fk_recovery_outcomes_action_merchant",
            ondelete="CASCADE",
        ),
        Index("ix_recovery_outcomes_merchant_case", "merchant_id", "recovery_case_id"),
        Index("ix_recovery_outcomes_merchant_status", "merchant_id", "status"),
        Index("ix_recovery_outcomes_merchant_verification", "merchant_id", "verification_status"),
    )

    # Primary key uses composite or dedicated ID; recovery_action_id is unique
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recovery_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recovery_action_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_recovered_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="UNVERIFIED"
    )
    verification_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
