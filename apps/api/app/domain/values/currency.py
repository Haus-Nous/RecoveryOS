"""Currency representation and ISO-4217 validation."""

from enum import StrEnum

from app.domain.exceptions import InvalidCurrencyError


class Currency(StrEnum):
    """Supported ISO-4217 currency representations."""

    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

    @classmethod
    def from_str(cls, value: str) -> "Currency":
        """Parse and validate currency code."""
        if not isinstance(value, str):
            raise InvalidCurrencyError(f"Currency must be a string, got {type(value).__name__}")
        normalized = value.strip().upper()
        try:
            return cls(normalized)
        except ValueError as err:
            raise InvalidCurrencyError(
                f"Unsupported currency code '{value}'. Must be one of {[c.value for c in cls]}"
            ) from err
