"""SQLAlchemy model for Payment Provider Connections."""

from datetime import datetime

from sqlalchemy import (
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


class PaymentProviderConnectionModel(Base):
    """Merchant-owned payment provider connection model."""

    __tablename__ = "payment_provider_connections"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="UNVERIFIED")
    key_id_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="1")

    __table_args__ = (
        UniqueConstraint(
            "merchant_id",
            "provider",
            "mode",
            "credential_ref",
            name="uq_payment_provider_connections_merchant_provider_mode_ref",
        ),
        CheckConstraint(
            "provider IN ('RAZORPAY')",
            name="ck_provider_connections_provider",
        ),
        CheckConstraint(
            "mode IN ('TEST', 'LIVE')",
            name="ck_provider_connections_mode",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED', 'UNVERIFIED')",
            name="ck_provider_connections_status",
        ),
        Index("ix_payment_provider_connections_merchant_status", "merchant_id", "status"),
    )
