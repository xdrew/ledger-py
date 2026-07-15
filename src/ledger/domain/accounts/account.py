"""The ``Account`` aggregate — an event-sourced balance with two buckets:
``available`` (spendable) and ``reserved`` (held pending settlement).

Invariants (enforced on the command side, never in ``_apply``):

* operations require the account to be ``OPEN``;
* amounts must be positive and currency-matched;
* ``available`` never goes negative; a debit only draws from ``reserved``;
* closing requires both buckets empty.
"""

from enum import StrEnum
from typing import Self
from uuid import UUID

from ledger.domain.accounts.events import (
    AccountClosed,
    AccountCredited,
    AccountDebited,
    AccountEvent,
    AccountFrozen,
    AccountOpened,
    FundsDeposited,
    FundsHeld,
    HoldReleased,
)
from ledger.domain.shared.aggregate import AggregateRoot
from ledger.domain.shared.errors import (
    AccountNotActive,
    AccountNotEmpty,
    CurrencyMismatch,
    InsufficientFunds,
    InvalidTransition,
)
from ledger.domain.shared.identifiers import AccountId
from ledger.domain.shared.money import CurrencyCode, Money

_UNSET_CURRENCY: CurrencyCode = "XXX"  # ISO 4217 "no currency" — placeholder pre-open


class AccountStatus(StrEnum):
    OPEN = "open"
    FROZEN = "frozen"
    CLOSED = "closed"


class Account(AggregateRoot[AccountEvent]):
    def __init__(self) -> None:
        super().__init__()
        self.account_id: AccountId | None = None
        self.currency: CurrencyCode = _UNSET_CURRENCY
        # A fresh, unopened aggregate is inert until AccountOpened is applied.
        self.status: AccountStatus = AccountStatus.CLOSED
        self.available: Money = Money.zero(_UNSET_CURRENCY)
        self.reserved: Money = Money.zero(_UNSET_CURRENCY)
        # Idempotency keys of balance-moving operations already applied. Lets a
        # replayed saga step (Temporal activity retry) become a safe no-op.
        self._applied_ops: set[UUID] = set()

    # --- construction ---

    @classmethod
    def open(cls, account_id: AccountId, currency: CurrencyCode) -> Self:
        account = cls()
        account.account_id = account_id
        account._record(AccountOpened(currency=currency))
        return account

    # --- commands ---

    def deposit(self, amount: Money) -> None:
        self._assert_operational(amount)
        self._record(FundsDeposited(amount=amount))

    def hold(self, amount: Money, operation_id: UUID) -> None:
        self._assert_operational(amount)
        if operation_id in self._applied_ops:
            return
        if self.available < amount:
            raise InsufficientFunds(f"hold {amount} exceeds available {self.available}")
        self._record(FundsHeld(amount=amount, operation_id=operation_id))

    def release_hold(self, amount: Money, operation_id: UUID) -> None:
        self._assert_operational(amount)
        if operation_id in self._applied_ops:
            return
        if self.reserved < amount:
            raise InsufficientFunds(f"release {amount} exceeds reserved {self.reserved}")
        self._record(HoldReleased(amount=amount, operation_id=operation_id))

    def debit(self, amount: Money, operation_id: UUID) -> None:
        """Finalize an outflow: draw from the held (reserved) bucket."""
        self._assert_operational(amount)
        if operation_id in self._applied_ops:
            return
        if self.reserved < amount:
            raise InsufficientFunds(f"debit {amount} exceeds reserved {self.reserved}")
        self._record(AccountDebited(amount=amount, operation_id=operation_id))

    def credit(self, amount: Money, operation_id: UUID) -> None:
        """Receive an inflow into the available bucket."""
        self._assert_operational(amount)
        if operation_id in self._applied_ops:
            return
        self._record(AccountCredited(amount=amount, operation_id=operation_id))

    def freeze(self) -> None:
        if self.status is not AccountStatus.OPEN:
            raise InvalidTransition(f"cannot freeze a {self.status} account")
        self._record(AccountFrozen())

    def close(self) -> None:
        if self.status is AccountStatus.CLOSED:
            raise InvalidTransition("account already closed")
        if self.available.amount != 0 or self.reserved.amount != 0:
            raise AccountNotEmpty(
                f"cannot close: available={self.available}, reserved={self.reserved}"
            )
        self._record(AccountClosed())

    # --- guards ---

    def _assert_operational(self, amount: Money) -> None:
        if self.status is not AccountStatus.OPEN:
            raise AccountNotActive(f"account is {self.status}")
        amount.assert_positive()
        if amount.currency != self.currency:
            raise CurrencyMismatch(f"account currency {self.currency} != {amount.currency}")

    # --- state transition (the single mutation point) ---

    def _apply(self, event: AccountEvent) -> None:
        match event:
            case AccountOpened(currency=currency):
                self.currency = currency
                self.status = AccountStatus.OPEN
                self.available = Money.zero(currency)
                self.reserved = Money.zero(currency)
            case FundsDeposited(amount=amount):
                self.available = self.available.add(amount)
            case FundsHeld(amount=amount, operation_id=operation_id):
                self._applied_ops.add(operation_id)
                self.available = self.available.subtract(amount)
                self.reserved = self.reserved.add(amount)
            case HoldReleased(amount=amount, operation_id=operation_id):
                self._applied_ops.add(operation_id)
                self.reserved = self.reserved.subtract(amount)
                self.available = self.available.add(amount)
            case AccountDebited(amount=amount, operation_id=operation_id):
                self._applied_ops.add(operation_id)
                self.reserved = self.reserved.subtract(amount)
            case AccountCredited(amount=amount, operation_id=operation_id):
                self._applied_ops.add(operation_id)
                self.available = self.available.add(amount)
            case AccountFrozen():
                self.status = AccountStatus.FROZEN
            case AccountClosed():
                self.status = AccountStatus.CLOSED
