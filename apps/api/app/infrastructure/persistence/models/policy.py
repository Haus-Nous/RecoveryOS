"""SQLAlchemy model for merchant policies."""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class PolicyModel(Base):
    """Persisted merchant guardrail policy aggregate."""

    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("max_retry_attempts >= 0", name="ck_policies_max_retries_non_negative"),
        CheckConstraint("cooldown_seconds >= 0", name="ck_policies_cooldown_non_negative"),
        CheckConstraint(
            "auto_action_amount_limit_minor >= 0", name="ck_policies_auto_limit_non_negative"
        ),
        CheckConstraint(
            "review_required_above_minor >= 0", name="ck_policies_review_limit_non_negative"
        ),
        CheckConstraint(
            "auto_action_amount_limit_minor <= review_required_above_minor",
            name="ck_policies_auto_limit_le_review_limit",
        ),
        CheckConstraint("length(currency) = 3", name="ck_policies_currency_iso3"),
        Index("ix_policies_merchant_enabled", "merchant_id", "enabled"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("merchants.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_retry_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    auto_action_amount_limit_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    review_required_above_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    allowed_strategies: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
