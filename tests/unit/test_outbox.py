"""Unit tests for the outbox relay."""

import asyncio

import pytest

from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.identifiers import new_account_id, new_event_id
from ledger.domain.shared.money import Money
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.records import StoredEvent
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository
from ledger.outbox.relay import OutboxRelay, run_relay
from ledger.projections.runner import InMemoryCheckpointStore


class CollectingPublisher:
    def __init__(self) -> None:
        self.events: list[StoredEvent] = []

    async def publish(self, event: StoredEvent) -> None:
        self.events.append(event)


async def _seed() -> InMemoryEventStore:
    registry = build_event_registry()
    store = InMemoryEventStore(registry)
    repo: EventSourcedRepository[Account] = EventSourcedRepository(
        store=store, registry=registry, stream_type=ACCOUNT_STREAM, factory=Account
    )
    account_id = new_account_id()
    account = Account.open(account_id, "USD")
    account.deposit(Money(amount=1000, currency="USD"))
    account.hold(Money(amount=400, currency="USD"), new_event_id())
    await repo.save(account_id, account)
    return store


class TestOutboxRelay:
    async def test_publishes_all_in_global_order(self) -> None:
        store = await _seed()
        publisher = CollectingPublisher()
        relay = OutboxRelay(
            store=store,
            checkpoints=InMemoryCheckpointStore(),
            publisher=publisher,
        )
        handled = await relay.drain()
        assert handled == 3
        positions = [e.global_position for e in publisher.events]
        assert positions == sorted(positions)
        assert [e.event_type for e in publisher.events] == [
            "AccountOpened",
            "FundsDeposited",
            "FundsHeld",
        ]

    async def test_checkpoint_makes_relay_idempotent(self) -> None:
        store = await _seed()
        publisher = CollectingPublisher()
        checkpoints = InMemoryCheckpointStore()
        relay = OutboxRelay(store=store, checkpoints=checkpoints, publisher=publisher)
        await relay.drain()
        assert await checkpoints.load("outbox") == 3
        # Second drain publishes nothing new.
        assert await relay.run_once() == 0
        assert len(publisher.events) == 3

    async def test_run_relay_publishes_then_stops_cleanly(self) -> None:
        store = await _seed()
        publisher = CollectingPublisher()
        relay = OutboxRelay(store=store, checkpoints=InMemoryCheckpointStore(), publisher=publisher)
        task = asyncio.create_task(run_relay(relay, poll_seconds=0.01))
        try:
            for _ in range(200):
                if len(publisher.events) >= 3:
                    break
                await asyncio.sleep(0.01)
            assert len(publisher.events) == 3  # the running loop published the backlog
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
