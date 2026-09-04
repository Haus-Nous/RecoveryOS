"""Immutable Domain Event definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.types import DomainEventId, ensure_utc_datetime, generate_id


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base immutable domain event representing a historical business fact."""

    event_id: DomainEventId
    event_type: str
    aggregate_id: str
    aggregate_type: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurred_at", ensure_utc_datetime(self.occurred_at))
        if not self.event_type or not self.event_type.strip():
            raise ValueError("DomainEvent event_type cannot be empty.")
        if not self.aggregate_id or not self.aggregate_id.strip():
            raise ValueError("DomainEvent aggregate_id cannot be empty.")
        if not self.aggregate_type or not self.aggregate_type.strip():
            raise ValueError("DomainEvent aggregate_type cannot be empty.")

    @classmethod
    def create(
        cls,
        event_type: str,
        aggregate_id: str,
        aggregate_type: str,
        occurred_at: datetime,
        payload: dict[str, Any] | None = None,
        event_id: DomainEventId | None = None,
    ) -> "DomainEvent":
        """Factory helper creating an event with auto-generated ID if omitted."""
        eid = event_id or DomainEventId(generate_id("evt"))
        return cls(
            event_id=eid,
            event_type=event_type,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            occurred_at=occurred_at,
            payload=payload or {},
        )
