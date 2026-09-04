"""Tests for financial timestamp timezone-awareness and UTC normalization."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.exceptions import InvalidTimestampError
from app.domain.types import ensure_utc_datetime


def test_accept_utc_aware_datetime() -> None:
    dt = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)
    normalized = ensure_utc_datetime(dt)
    assert normalized == dt
    assert normalized.tzinfo == UTC


def test_normalize_non_utc_aware_datetime() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    dt_ist = datetime(2026, 9, 4, 17, 30, 0, tzinfo=ist)
    normalized = ensure_utc_datetime(dt_ist)
    assert normalized.tzinfo == UTC
    assert normalized.hour == 12
    assert normalized.minute == 0


def test_reject_naive_datetime() -> None:
    naive = datetime(2026, 9, 4, 12, 0, 0)
    with pytest.raises(InvalidTimestampError) as exc_info:
        ensure_utc_datetime(naive)
    assert "Financial timestamps must be timezone-aware" in str(exc_info.value)
