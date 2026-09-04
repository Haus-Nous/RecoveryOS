"""Bi-directional mapper for DomainEvent domain entity and DomainEventModel."""

from datetime import UTC, datetime

from app.application.exceptions import DataCorruptionError
from app.domain.events.base import DomainEvent
from app.domain.types import DomainEventId
from app.infrastructure.persistence.models.domain_event import DomainEventModel


class DomainEventMapper:
    """Explicit mapping between DomainEvent domain object and DomainEventModel ORM entity."""

    @staticmethod
    def to_domain(model: DomainEventModel) -> DomainEvent:
        """Map ORM DomainEventModel to immutable pure DomainEvent domain object."""
        try:
            occurred_at = model.occurred_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)

            return DomainEvent(
                event_id=DomainEventId(model.event_id),
                event_type=model.event_type,
                aggregate_id=model.aggregate_id,
                aggregate_type=model.aggregate_type,
                occurred_at=occurred_at,
                payload=dict(model.payload),
            )
        except Exception as exc:
            raise DataCorruptionError("DomainEvent", model.event_id, str(exc)) from exc

    @staticmethod
    def to_model(
        domain: DomainEvent,
        merchant_id: str | None = None,
        recorded_at: datetime | None = None,
    ) -> DomainEventModel:
        """Map immutable pure DomainEvent domain object to ORM DomainEventModel."""
        rec_at = recorded_at or datetime.now(UTC)
        if rec_at.tzinfo is None:
            rec_at = rec_at.replace(tzinfo=UTC)

        return DomainEventModel(
            event_id=str(domain.event_id),
            merchant_id=merchant_id,
            aggregate_type=domain.aggregate_type,
            aggregate_id=domain.aggregate_id,
            event_type=domain.event_type,
            occurred_at=domain.occurred_at,
            payload=dict(domain.payload),
            recorded_at=rec_at,
        )
