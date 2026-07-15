"""Account domain events. The account id is carried by the event stream, so the
payloads hold only what changes.

Balance-moving events carry an ``operation_id`` — the idempotency key that lets
the aggregate ignore a replayed saga step (see ``Account``)."""

from uuid import UUID

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.money import CurrencyCode, Money


class AccountOpened(DomainEvent):
    currency: CurrencyCode


class FundsDeposited(DomainEvent):
    amount: Money


class FundsHeld(DomainEvent):
    amount: Money
    operation_id: UUID


class HoldReleased(DomainEvent):
    amount: Money
    operation_id: UUID


class AccountDebited(DomainEvent):
    amount: Money
    operation_id: UUID


class AccountCredited(DomainEvent):
    amount: Money
    operation_id: UUID


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
