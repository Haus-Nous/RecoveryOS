"""Money value object with strict minor unit precision.

CRITICAL INVARIANT:
Never represent financial values with float.
All amounts are stored as exact integers in minor units (e.g. paise for INR, cents for USD).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.exceptions import CurrencyMismatchError, InvalidMoneyError
from app.domain.values.currency import Currency


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable monetary value object stored strictly in minor units."""

    amount_minor: int
    currency: Currency

    def __post_init__(self) -> None:
        # Prevent boolean masquerading as int (in Python, isinstance(True, int) is True)
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise InvalidMoneyError(
                f"Monetary amount_minor must be an integer, got {type(self.amount_minor).__name__} "
                "(floats strictly forbidden)."
            )
        if not isinstance(self.currency, Currency):
            raise InvalidMoneyError(
                f"Monetary currency must be a Currency instance, got {type(self.currency).__name__}"
            )

    @classmethod
    def from_minor(
        cls,
        amount_minor: int,
        currency: Currency | str,
        allow_negative: bool = False,
    ) -> "Money":
        """Factory creating Money from integer minor units."""
        curr = Currency.from_str(currency) if isinstance(currency, str) else currency
        if not allow_negative and amount_minor < 0:
            raise InvalidMoneyError(f"Negative monetary amount ({amount_minor}) is not permitted.")
        return cls(amount_minor=amount_minor, currency=curr)

    @classmethod
    def from_major_decimal(
        cls,
        amount_major: Decimal | int,
        currency: Currency | str,
        allow_negative: bool = False,
    ) -> "Money":
        """Factory creating Money from a Decimal major currency unit without float conversion."""
        if isinstance(amount_major, float):
            raise InvalidMoneyError(
                "Float input to from_major_decimal is strictly prohibited. Use Decimal or int."
            )
        if not isinstance(amount_major, (Decimal, int)) or isinstance(amount_major, bool):
            raise InvalidMoneyError(f"Expected Decimal or int, got {type(amount_major).__name__}")

        dec = Decimal(str(amount_major))
        # Multiply by 100 for 2-decimal currencies (INR/USD/EUR/GBP)
        minor = int(dec * 100)
        return cls.from_minor(amount_minor=minor, currency=currency, allow_negative=allow_negative)

    @classmethod
    def zero(cls, currency: Currency | str = Currency.INR) -> "Money":
        """Return zero Money in specified currency."""
        curr = Currency.from_str(currency) if isinstance(currency, str) else currency
        return cls(amount_minor=0, currency=curr)

    def _ensure_same_currency(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise InvalidMoneyError(f"Cannot operate with non-Money type {type(other).__name__}")
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency.value, other.currency.value)

    def __add__(self, other: "Money") -> "Money":
        self._ensure_same_currency(other)
        return Money(amount_minor=self.amount_minor + other.amount_minor, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._ensure_same_currency(other)
        return Money(amount_minor=self.amount_minor - other.amount_minor, currency=self.currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        if isinstance(factor, (float, bool)) or not isinstance(factor, (int, Decimal)):
            raise InvalidMoneyError(
                f"Multiplication only allowed with int/Decimal, got {type(factor).__name__}"
            )
        if isinstance(factor, int):
            return Money(amount_minor=self.amount_minor * factor, currency=self.currency)
        # Decimal factor
        product = int(Decimal(self.amount_minor) * factor)
        return Money(amount_minor=product, currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self.amount_minor < other.amount_minor

    def __le__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self.amount_minor <= other.amount_minor

    def __gt__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self.amount_minor > other.amount_minor

    def __ge__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self.amount_minor >= other.amount_minor

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return False
        return self.amount_minor == other.amount_minor and self.currency == other.currency

    def is_zero(self) -> bool:
        return self.amount_minor == 0

    def is_positive(self) -> bool:
        return self.amount_minor > 0

    def is_negative(self) -> bool:
        return self.amount_minor < 0

    def to_major_decimal(self) -> Decimal:
        """Convert minor units to Decimal major units (e.g. 10050 -> 100.50)."""
        return Decimal(self.amount_minor) / Decimal(100)

    def __str__(self) -> str:
        major = self.to_major_decimal()
        symbol = "₹" if self.currency == Currency.INR else f"{self.currency.value} "
        return f"{symbol}{major:.2f}"

    def __repr__(self) -> str:
        return f"Money({self.amount_minor} minor units {self.currency.value})"
