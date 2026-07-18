"""Property-based tests for the ``Money`` value object invariants."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ledger.domain.shared.errors import CurrencyMismatch
from ledger.domain.shared.money import Money

# Bounded to a wide but sane integer range for minor units.
amounts = st.integers(min_value=-(10**15), max_value=10**15)
currencies = st.sampled_from(["USD", "EUR", "GBP", "JPY"])


@given(a=amounts, b=amounts, cur=currencies)
def test_add_then_subtract_round_trips(a: int, b: int, cur: str) -> None:
    x, y = Money(amount=a, currency=cur), Money(amount=b, currency=cur)
    assert x.add(y).subtract(y) == x


@given(a=amounts, cur=currencies)
def test_negate_is_involution(a: int, cur: str) -> None:
    x = Money(amount=a, currency=cur)
    assert x.negate().negate() == x


@given(a=amounts, cur=currencies)
def test_zero_is_additive_identity(a: int, cur: str) -> None:
    x = Money(amount=a, currency=cur)
    assert x.add(Money.zero(cur)) == x
    assert x.subtract(Money.zero(cur)) == x


@given(a=amounts, b=amounts, cur=currencies)
def test_ordering_agrees_with_integer_amounts(a: int, b: int, cur: str) -> None:
    x, y = Money(amount=a, currency=cur), Money(amount=b, currency=cur)
    assert (x < y) == (a < b)
    assert (x <= y) == (a <= b)


@given(a=amounts, b=amounts)
def test_cross_currency_operations_raise(a: int, b: int) -> None:
    usd, eur = Money(amount=a, currency="USD"), Money(amount=b, currency="EUR")
    for op in (usd.add, usd.subtract):
        with pytest.raises(CurrencyMismatch):
            op(eur)
    with pytest.raises(CurrencyMismatch):
        _ = usd < eur
