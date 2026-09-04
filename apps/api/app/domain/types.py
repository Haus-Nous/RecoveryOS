"""Domain identifiers, time utilities, and foundational types."""

import uuid
from datetime import UTC, datetime
from typing import NewType

from app.domain.exceptions import InvalidTimestampError


def ensure_utc_datetime(dt: datetime) -> datetime:
    """Validate that a datetime is timezone-aware and convert it to UTC.

    Raises:
        InvalidTimestampError: If the datetime object is naive.
    """
    if not isinstance(dt, datetime):
        raise InvalidTimestampError(f"Expected datetime instance, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise InvalidTimestampError(
            "Financial timestamps must be timezone-aware (naive datetimes rejected)."
        )
    return dt.astimezone(UTC)


def generate_id(prefix: str) -> str:
    """Generate a standard UUID-backed prefixed domain identifier."""
    return f"{prefix}_{uuid.uuid4().hex}"


OrderId = NewType("OrderId", str)
PaymentId = NewType("PaymentId", str)
RecoveryCaseId = NewType("RecoveryCaseId", str)
RecoveryProposalId = NewType("RecoveryProposalId", str)
RecoveryActionId = NewType("RecoveryActionId", str)
PolicyId = NewType("PolicyId", str)
DomainEventId = NewType("DomainEventId", str)
MerchantId = NewType("MerchantId", str)
