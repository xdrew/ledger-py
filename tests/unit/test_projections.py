"""Unit tests for the CQRS read side: projections + runner + checkpoints."""

import asyncio
from uuid import UUID

from ledger.domain.accounts.account import Account, AccountStatus
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.identifiers import new_account_id, new_event_id
from ledger.domain.shared.money import Money
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.records import StoredEvent
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository
from ledger.projections.read_models import (
    AccountBalancesProjection,
    AccountStatementProjection,
)
from ledger.projections.read_models_service import ReadModels
from ledger.projections.runner import InMemoryCheckpointStore, ProjectionRunner


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


class _YieldingStore:
    """Wraps a store but makes ``read_all`` yield, exposing catch-up races."""

    def __init__(self, inner: InMemoryEventStore) -> None:
        self._inner = inner

    async def read_all(self, *, from_position: int = 0, limit: int = 500) -> list[StoredEvent]:
        await asyncio.sleep(0)  # yield → let a concurrent drain interleave
        return await self._inner.read_all(from_position=from_position, limit=limit)

    async def load_stream(self, *, stream_type: str, stream_id: UUID) -> list[StoredEvent]:
        return await self._inner.load_stream(stream_type=stream_type, stream_id=stream_id)

    async def append(self, **kwargs: object) -> list[StoredEvent]:  # pragma: no cover - unused
        raise NotImplementedError


async def _seed_account() -> tuple[InMemoryEventStore, object]:
    registry = build_event_registry()
    store = InMemoryEventStore(registry)
    repo: EventSourcedRepository[Account] = EventSourcedRepository(
        store=store, registry=registry, stream_type=ACCOUNT_STREAM, factory=Account
    )
    account_id = new_account_id()
    account = Account.open(account_id, "USD")
    account.deposit(usd(1000))
    account.hold(usd(400), new_event_id())
    account.debit(usd(400), new_event_id())
    await repo.save(account_id, account)
    return store, account_id


class TestReadModelsConcurrency:
    async def test_concurrent_catch_up_applies_each_event_once(self) -> None:
        registry = build_event_registry()
        inner = InMemoryEventStore(registry)
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=inner, registry=registry, stream_type=ACCOUNT_STREAM, factory=Account
        )
        account_id = new_account_id()
        account = Account.open(account_id, "USD")
        account.deposit(usd(500))
        await repo.save(account_id, account)

        read_models = ReadModels(_YieldingStore(inner), registry)
        # Statement lines are appended (not reset like a balance), so a double-apply
        # shows up as duplicate lines — a reliable witness of the catch-up race.
        first, second = await asyncio.gather(
            read_models.statement_of(account_id),
            read_models.statement_of(account_id),
        )
        # Without the lock both drains read the same batch and append the deposit twice.
        assert [line.kind for line in first] == ["FundsDeposited"]
        assert [line.kind for line in second] == ["FundsDeposited"]


class TestProjections:
    async def test_balances_projection_matches_aggregate(self) -> None:
        store, account_id = await _seed_account()
        registry = build_event_registry()
        balances = AccountBalancesProjection(registry)
        runner = ProjectionRunner(
            store=store,
            checkpoints=InMemoryCheckpointStore(),
            name="balances",
            projectors=[balances],
        )
        handled = await runner.drain()
        assert handled == 4  # opened, deposited, held, debited

        view = balances.balance_of(account_id)  # type: ignore[arg-type]
        assert view is not None
        assert view.available == 600
        assert view.reserved == 0
        assert view.total == 600
        assert view.status is AccountStatus.OPEN

    async def test_statement_projection_lists_movements(self) -> None:
        store, account_id = await _seed_account()
        statement = AccountStatementProjection()
        runner = ProjectionRunner(
            store=store,
            checkpoints=InMemoryCheckpointStore(),
            name="statement",
            projectors=[statement],
        )
        await runner.drain()

        lines = statement.statement_of(account_id)  # type: ignore[arg-type]
        assert [line.kind for line in lines] == [
            "FundsDeposited",
            "FundsHeld",
            "AccountDebited",
        ]
        assert lines[0].amount == 1000

    async def test_release_freeze_and_close_reflected(self) -> None:
        registry = build_event_registry()
        store = InMemoryEventStore(registry)
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=store, registry=registry, stream_type=ACCOUNT_STREAM, factory=Account
        )
        # Account A: deposit, hold, release, then freeze.
        a_id = new_account_id()
        account_a = Account.open(a_id, "USD")
        account_a.deposit(usd(1000))
        account_a.hold(usd(400), new_event_id())
        account_a.release_hold(usd(400), new_event_id())
        account_a.freeze()
        await repo.save(a_id, account_a)
        # Account B: opened, then closed while empty.
        b_id = new_account_id()
        account_b = Account.open(b_id, "USD")
        account_b.close()
        await repo.save(b_id, account_b)

        balances = AccountBalancesProjection(registry)
        runner = ProjectionRunner(
            store=store,
            checkpoints=InMemoryCheckpointStore(),
            name="balances",
            projectors=[balances],
        )
        await runner.drain()

        view_a = balances.balance_of(a_id)
        assert view_a is not None
        assert view_a.available == 1000
        assert view_a.reserved == 0
        assert view_a.status is AccountStatus.FROZEN
        # snapshot() (the AccountStatusReader port) reflects the frozen status.
        snap_a = await balances.snapshot(a_id)
        assert snap_a is not None
        assert snap_a.status is AccountStatus.FROZEN

        view_b = balances.balance_of(b_id)
        assert view_b is not None
        assert view_b.status is AccountStatus.CLOSED

    async def test_lookups_for_unknown_accounts(self) -> None:
        registry = build_event_registry()
        balances = AccountBalancesProjection(registry)
        statement = AccountStatementProjection()
        unknown = new_account_id()
        assert balances.balance_of(unknown) is None
        assert await balances.snapshot(unknown) is None
        assert statement.statement_of(unknown) == []

    async def test_checkpoint_advances_and_is_resumable(self) -> None:
        store, _ = await _seed_account()
        registry = build_event_registry()
        checkpoints = InMemoryCheckpointStore()
        balances = AccountBalancesProjection(registry)
        runner = ProjectionRunner(
            store=store,
            checkpoints=checkpoints,
            name="balances",
            projectors=[balances],
        )
        await runner.drain()
        assert await checkpoints.load("balances") == 4
        # A second drain is a no-op — checkpoint already at the head.
        assert await runner.run_once() == 0
