"""SQLAlchemy model for recovery actions."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class RecoveryActionModel(Base):
    """Persisted recovery action aggregate.

    INVARIANT: Cannot be queued/executing without ALLOW authorization decision.
    """

    __tablename__ = "recovery_actions"
    __table_args__ = (
        CheckConstraint("attempt_number >= 1", name="ck_recovery_actions_attempt_positive"),
        # DB-level invariant check: Executable actions MUST have ALLOW decision
        CheckConstraint(
            "(state NOT IN ('QUEUED', 'EXECUTING')) OR (authorization_decision = 'ALLOW')",
            name="ck_recovery_actions_executable_must_be_allowed",
        ),
        Index("ix_recovery_actions_merchant_case", "merchant_id", "recovery_case_id"),
        Index("ix_recovery_actions_merchant_state", "merchant_id", "state"),
        Index("ix_recovery_actions_merchant_created_at", "merchant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recovery_case_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    authorization_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    authorization_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
