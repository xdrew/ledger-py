"""Account domain events. The account id is carried by the event stream, so the
payloads hold only what changes."""

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.money import CurrencyCode, Money


class AccountOpened(DomainEvent):
    currency: CurrencyCode


class FundsDeposited(DomainEvent):
    amount: Money


class FundsHeld(DomainEvent):
    amount: Money


class HoldReleased(DomainEvent):
    amount: Money


class AccountDebited(DomainEvent):
    amount: Money


class AccountCredited(DomainEvent):
    amount: Money


class AccountFrozen(DomainEvent):
    pass


class AccountClosed(DomainEvent):
    pass


type AccountEvent = (
    AccountOpened
    | FundsDeposited
    | FundsHeld
    | HoldReleased
    | AccountDebited
    | AccountCredited
    | AccountFrozen
    | AccountClosed
)

ACCOUNT_STREAM = "account"

ACCOUNT_EVENT_TYPES: tuple[type[DomainEvent], ...] = (
    AccountOpened,
    FundsDeposited,
    FundsHeld,
    HoldReleased,
    AccountDebited,
    AccountCredited,
    AccountFrozen,
    AccountClosed,
)
