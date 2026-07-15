"""``Money`` value object — an integer amount in minor units plus an ISO-4217
currency. Immutable; arithmetic is currency-checked and total-ordered.
"""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints

from ledger.domain.shared.errors import CurrencyMismatch, InvalidAmount

CurrencyCode = Annotated[str, StringConstraints(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")]


class Money(BaseModel):
    """An amount of money in minor units (e.g. cents), tagged with a currency.

    Amounts are signed integers: balances stay non-negative by domain rule,
    while journal legs use sign to express debit/credit direction.
    """

    model_config = ConfigDict(frozen=True)

    amount: int
    currency: CurrencyCode

    @classmethod
    def zero(cls, currency: CurrencyCode) -> Self:
        return cls(amount=0, currency=currency)

    def _assert_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"cannot combine {self.currency} with {other.currency}")

    def add(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: Money) -> Money:
        self._assert_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def negate(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    def assert_positive(self) -> Money:
        """Return self if strictly positive, else raise ``InvalidAmount``."""
        if self.amount <= 0:
            raise InvalidAmount(f"amount must be positive, got {self.amount}")
        return self

    def __lt__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
