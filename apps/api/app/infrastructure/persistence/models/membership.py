"""SQLAlchemy model for Merchant Memberships."""

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


class MerchantMembershipModel(Base):
    """Merchant membership entity model binding users to merchant tenants."""

    __tablename__ = "merchant_memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="1")

    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", name="uq_merchant_memberships_merchant_user"),
        CheckConstraint(
            "role IN ('OWNER', 'ADMIN', 'OPERATOR', 'ANALYST', 'AUDITOR')",
            name="ck_merchant_memberships_role",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INVITED', 'SUSPENDED', 'REVOKED')",
            name="ck_merchant_memberships_status",
        ),
        Index("ix_merchant_memberships_merchant_status", "merchant_id", "status"),
        Index("ix_merchant_memberships_user_status", "user_id", "status"),
    )
