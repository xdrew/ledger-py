"""Unit tests for the Account aggregate and its persistence round-trip."""

from uuid import UUID

import pytest

from ledger.domain.accounts.account import Account, AccountStatus
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.errors import (
    AccountNotActive,
    AccountNotEmpty,
    CurrencyMismatch,
    InsufficientFunds,
    InvalidTransition,
)
from ledger.domain.shared.identifiers import new_account_id, new_event_id
from ledger.domain.shared.money import Money
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


def op() -> UUID:
    return new_event_id()


class TestAccountCommands:
    def test_open_starts_empty_and_open(self) -> None:
        account = Account.open(new_account_id(), "USD")
        assert account.status is AccountStatus.OPEN
        assert account.available == usd(0)
        assert account.reserved == usd(0)

    def test_deposit_increases_available(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        assert account.available == usd(1000)

    def test_hold_moves_available_to_reserved(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        account.hold(usd(400), op())
        assert account.available == usd(600)
        assert account.reserved == usd(400)

    def test_hold_beyond_available_rejected(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(100))
        with pytest.raises(InsufficientFunds):
            account.hold(usd(101), op())

    def test_release_hold_returns_to_available(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        account.hold(usd(400), op())
        account.release_hold(usd(400), op())
        assert account.available == usd(1000)
        assert account.reserved == usd(0)

    def test_debit_draws_from_reserved(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        account.hold(usd(400), op())
        account.debit(usd(400), op())  # settle the hold
        assert account.available == usd(600)
        assert account.reserved == usd(0)

    def test_debit_beyond_reserved_rejected(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        account.hold(usd(100), op())
        with pytest.raises(InsufficientFunds):
            account.debit(usd(200), op())

    def test_release_beyond_reserved_rejected(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        account.hold(usd(100), op())
        with pytest.raises(InsufficientFunds):
            account.release_hold(usd(200), op())

    def test_credit_increases_available(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.credit(usd(500), op())
        assert account.available == usd(500)

    def test_repeated_operation_id_is_idempotent(self) -> None:
        # A replayed saga step (same operation_id) must not double-apply.
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(1000))
        hold_op = op()
        account.hold(usd(400), hold_op)
        account.hold(usd(400), hold_op)  # retry — no-op
        account.hold(usd(400), hold_op)  # retry — no-op
        assert account.available == usd(600)
        assert account.reserved == usd(400)

    def test_currency_mismatch_rejected(self) -> None:
        account = Account.open(new_account_id(), "USD")
        with pytest.raises(CurrencyMismatch):
            account.deposit(Money(amount=1, currency="EUR"))

    def test_frozen_blocks_operations(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(100))
        account.freeze()
        assert account.status is AccountStatus.FROZEN
        with pytest.raises(AccountNotActive):
            account.deposit(usd(1))

    def test_cannot_freeze_twice(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.freeze()
        with pytest.raises(InvalidTransition):
            account.freeze()

    def test_close_requires_empty(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.deposit(usd(100))
        with pytest.raises(AccountNotEmpty):
            account.close()

    def test_close_empty_account(self) -> None:
        account = Account.open(new_account_id(), "USD")
        account.close()
        assert account.status is AccountStatus.CLOSED
        with pytest.raises(InvalidTransition):
            account.close()


class TestAccountPersistence:
    async def test_round_trip_through_repository(self) -> None:
        store = InMemoryEventStore(build_event_registry())
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=store,
            registry=build_event_registry(),
            stream_type=ACCOUNT_STREAM,
            factory=Account,
        )
        account_id = new_account_id()
        account = Account.open(account_id, "USD")
        account.deposit(usd(1000))
        account.hold(usd(400), op())
        await repo.save(account_id, account)

        reloaded = await repo.load(account_id)
        assert reloaded is not None
        assert reloaded.available == usd(600)
        assert reloaded.reserved == usd(400)
        assert reloaded.version == 3  # opened + deposited + held

    async def test_load_missing_returns_none(self) -> None:
        store = InMemoryEventStore(build_event_registry())
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=store,
            registry=build_event_registry(),
            stream_type=ACCOUNT_STREAM,
            factory=Account,
        )
        assert await repo.load(new_account_id()) is None

    async def test_save_without_changes_is_noop(self) -> None:
        registry = build_event_registry()
        store = InMemoryEventStore(registry)
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=store, registry=registry, stream_type=ACCOUNT_STREAM, factory=Account
        )
        account_id = new_account_id()
        await repo.save(account_id, Account.open(account_id, "USD"))

        reloaded = await repo.load(account_id)
        assert reloaded is not None
        appended = await repo.save(account_id, reloaded)  # no pending events
        assert appended == []
