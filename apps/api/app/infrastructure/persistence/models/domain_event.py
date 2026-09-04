"""SQLAlchemy model for the immutable append-only domain event log."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.models.base import Base


class DomainEventModel(Base):
    """Persisted immutable domain event in the event log."""

    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id", "occurred_at"),
        Index("ix_domain_events_merchant_occurred_at", "merchant_id", "occurred_at"),
        Index("ix_domain_events_event_type", "event_type"),
    )

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
