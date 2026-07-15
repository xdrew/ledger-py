"""In-memory read models (projections) for accounts.

These are the query side of CQRS. ``AccountBalancesProjection`` doubles as the
:class:`AccountStatusReader` port the posting service depends on. The Postgres
implementations live behind the same shape in the infra layer.
"""

from dataclasses import dataclass, field
from datetime import datetime

from ledger.domain.accounts.account import AccountStatus
from ledger.domain.accounts.events import (
    ACCOUNT_STREAM,
    AccountClosed,
    AccountCredited,
    AccountDebited,
    AccountFrozen,
    AccountOpened,
    FundsDeposited,
    FundsHeld,
    HoldReleased,
)
from ledger.domain.ledger.posting_service import AccountSnapshot
from ledger.domain.shared.identifiers import AccountId
from ledger.eventstore.records import StoredEvent
from ledger.eventstore.serialization import EventRegistry


@dataclass(frozen=True, slots=True)
class AccountBalanceView:
    account_id: AccountId
    currency: str
    available: int
    reserved: int
    status: AccountStatus

    @property
    def total(self) -> int:
        return self.available + self.reserved


@dataclass
class _Balance:
    currency: str
    available: int = 0
    reserved: int = 0
    status: AccountStatus = AccountStatus.OPEN


class AccountBalancesProjection:
    """Projects account events into current balances; also serves as the
    ``AccountStatusReader`` used when posting journal entries."""

    def __init__(self, registry: EventRegistry) -> None:
        self._registry = registry
        self._by_id: dict[AccountId, _Balance] = {}

    async def project(self, event: StoredEvent) -> None:
        if event.stream_type != ACCOUNT_STREAM:
            return
        domain = self._registry.deserialize(
            event_type=event.event_type,
            schema_version=event.schema_version,
            payload=event.payload,
        )
        account_id = event.stream_id
        match domain:
            case AccountOpened(currency=currency):
                self._by_id[account_id] = _Balance(currency=currency)
            case FundsDeposited(amount=amount) | AccountCredited(amount=amount):
                self._by_id[account_id].available += amount.amount
            case FundsHeld(amount=amount):
                balance = self._by_id[account_id]
                balance.available -= amount.amount
                balance.reserved += amount.amount
            case HoldReleased(amount=amount):
                balance = self._by_id[account_id]
                balance.reserved -= amount.amount
                balance.available += amount.amount
            case AccountDebited(amount=amount):
                self._by_id[account_id].reserved -= amount.amount
            case AccountFrozen():
                self._by_id[account_id].status = AccountStatus.FROZEN
            case AccountClosed():
                self._by_id[account_id].status = AccountStatus.CLOSED
            case _:  # not an account event we track
                pass

    def balance_of(self, account_id: AccountId) -> AccountBalanceView | None:
        balance = self._by_id.get(account_id)
        if balance is None:
            return None
        return AccountBalanceView(
            account_id=account_id,
            currency=balance.currency,
            available=balance.available,
            reserved=balance.reserved,
            status=balance.status,
        )

    async def snapshot(self, account_id: AccountId) -> AccountSnapshot | None:
        balance = self._by_id.get(account_id)
        if balance is None:
            return None
        return AccountSnapshot(
            account_id=account_id, currency=balance.currency, status=balance.status
        )


@dataclass(frozen=True, slots=True)
class StatementLine:
    global_position: int
    kind: str
    amount: int
    currency: str
    occurred_at: datetime


@dataclass
class _Statement:
    lines: list[StatementLine] = field(default_factory=list[StatementLine])


class AccountStatementProjection:
    """Per-account ledger of balance-affecting events, in order."""

    _AMOUNT_EVENTS = frozenset(
        {
            "FundsDeposited",
            "FundsHeld",
            "HoldReleased",
            "AccountDebited",
            "AccountCredited",
        }
    )

    def __init__(self) -> None:
        self._by_id: dict[AccountId, _Statement] = {}

    async def project(self, event: StoredEvent) -> None:
        if event.stream_type != ACCOUNT_STREAM:
            return
        if event.event_type == "AccountOpened":
            self._by_id.setdefault(event.stream_id, _Statement())
            return
        if event.event_type not in self._AMOUNT_EVENTS:
            return
        amount = event.payload["amount"]
        self._by_id.setdefault(event.stream_id, _Statement()).lines.append(
            StatementLine(
                global_position=event.global_position,
                kind=event.event_type,
                amount=amount["amount"],
                currency=amount["currency"],
                occurred_at=event.occurred_at,
            )
        )

    def statement_of(self, account_id: AccountId) -> list[StatementLine]:
        statement = self._by_id.get(account_id)
        return list(statement.lines) if statement else []
