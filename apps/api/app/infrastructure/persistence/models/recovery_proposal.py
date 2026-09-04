"""SQLAlchemy model for diagnostic recovery proposals."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class RecoveryProposalModel(Base):
    """Persisted diagnostic recovery proposal.

    INVARIANT: Purely advisory recommendation.
    """

    __tablename__ = "recovery_proposals"
    __table_args__ = (
        CheckConstraint(
            "confidence_bps >= 0 AND confidence_bps <= 10000",
            name="ck_recovery_proposals_confidence_bps_range",
        ),
        Index("ix_recovery_proposals_merchant_case", "merchant_id", "recovery_case_id"),
        Index("ix_recovery_proposals_merchant_created_at", "merchant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recovery_case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
