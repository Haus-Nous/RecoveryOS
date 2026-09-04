"""Tests for Money and Currency value objects."""

from decimal import Decimal
from typing import Any

import pytest

from app.domain.exceptions import CurrencyMismatchError, InvalidCurrencyError, InvalidMoneyError
from app.domain.values.currency import Currency
from app.domain.values.money import Money


class TestCurrency:
    def test_valid_currencies(self) -> None:
        assert Currency.INR == "INR"
        assert Currency.USD == "USD"
        assert Currency.from_str("inr") == Currency.INR
        assert Currency.from_str("USD ") == Currency.USD

    def test_invalid_currency_raises(self) -> None:
        with pytest.raises(InvalidCurrencyError):
            Currency.from_str("INVALID")
        with pytest.raises(InvalidCurrencyError):
            invalid_raw: Any = 123
            Currency.from_str(invalid_raw)


class TestMoney:
    def test_valid_money_instantiation(self) -> None:
        m = Money.from_minor(10050, Currency.INR)
        assert m.amount_minor == 10050
        assert m.currency == Currency.INR
        assert m.to_major_decimal() == Decimal("100.50")
        assert "₹100.50" in str(m)

    def test_reject_float_amount_minor(self) -> None:
        float_val: Any = 100.50
        with pytest.raises(InvalidMoneyError):
            Money(amount_minor=float_val, currency=Currency.INR)

        with pytest.raises(InvalidMoneyError):
            Money.from_major_decimal(float_val, Currency.INR)

    def test_reject_bool_as_int(self) -> None:
        bool_val: Any = True
        with pytest.raises(InvalidMoneyError):
            Money(amount_minor=bool_val, currency=Currency.INR)

    def test_reject_negative_money_by_default(self) -> None:
        with pytest.raises(InvalidMoneyError):
            Money.from_minor(-500, Currency.INR)

    def test_allow_explicit_negative_money(self) -> None:
        m = Money.from_minor(-500, Currency.INR, allow_negative=True)
        assert m.amount_minor == -500
        assert m.is_negative()

    def test_zero_money(self) -> None:
        z = Money.zero(Currency.INR)
        assert z.is_zero()
        assert z.amount_minor == 0

    def test_addition_same_currency(self) -> None:
        m1 = Money.from_minor(1000, Currency.INR)
        m2 = Money.from_minor(2500, Currency.INR)
        res = m1 + m2
        assert res.amount_minor == 3500
        assert res.currency == Currency.INR

    def test_subtraction_same_currency(self) -> None:
        m1 = Money.from_minor(5000, Currency.INR)
        m2 = Money.from_minor(2000, Currency.INR)
        res = m1 - m2
        assert res.amount_minor == 3000
        assert res.currency == Currency.INR

    def test_currency_mismatch_on_addition_raises(self) -> None:
        inr = Money.from_minor(1000, Currency.INR)
        usd = Money.from_minor(1000, Currency.USD)
        with pytest.raises(CurrencyMismatchError):
            _ = inr + usd

    def test_currency_mismatch_on_subtraction_raises(self) -> None:
        inr = Money.from_minor(1000, Currency.INR)
        usd = Money.from_minor(1000, Currency.USD)
        with pytest.raises(CurrencyMismatchError):
            _ = inr - usd

    def test_currency_mismatch_on_comparison_raises(self) -> None:
        inr = Money.from_minor(1000, Currency.INR)
        usd = Money.from_minor(1000, Currency.USD)
        with pytest.raises(CurrencyMismatchError):
            _ = inr < usd

    def test_equality_and_comparisons(self) -> None:
        m1 = Money.from_minor(1000, Currency.INR)
        m2 = Money.from_minor(1000, Currency.INR)
        m3 = Money.from_minor(2000, Currency.INR)
        assert m1 == m2
        assert m1 != m3
        assert m1 < m3
        assert m3 > m1
        assert m1 <= m2
        assert m1 >= m2

    def test_multiplication_int_and_decimal_only(self) -> None:
        m = Money.from_minor(1000, Currency.INR)
        m_int = m * 3
        assert m_int.amount_minor == 3000

        m_dec = m * Decimal("1.5")
        assert m_dec.amount_minor == 1500

        invalid_mult: Any = 1.5
        with pytest.raises(InvalidMoneyError):
            _ = m * invalid_mult

        invalid_bool: Any = True
        with pytest.raises(InvalidMoneyError):
            _ = m * invalid_bool
