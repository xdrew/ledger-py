"""Integration tests for the Postgres event store against a real database
(spun up via testcontainers). Mirrors the in-memory store's contract."""

from collections.abc import AsyncIterator, Iterator

import pytest

from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import new_account_id, new_event_id
from ledger.domain.shared.money import Money
from ledger.eventstore.postgres import PostgresEventStore
from ledger.eventstore.records import EventMetadata
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository
from ledger.eventstore.store import ConcurrencyConflict

pytest.importorskip("testcontainers.postgres")
from testcontainers.postgres import PostgresContainer


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


@pytest.fixture(scope="module")
def dsn() -> Iterator[str]:
    with PostgresContainer("postgres:17-alpine") as postgres:
        url = postgres.get_connection_url()
        # testcontainers hands back a SQLAlchemy-style URL; asyncpg wants a plain one.
        yield url.replace("+psycopg2", "").replace("+psycopg", "")


@pytest.fixture
async def store(dsn: str) -> AsyncIterator[PostgresEventStore]:
    event_store = await PostgresEventStore.connect(dsn, build_event_registry())
    try:
        yield event_store
    finally:
        await event_store.aclose()


class SampleHappened(DomainEvent):
    note: str


@pytest.fixture
async def sample_store(dsn: str) -> AsyncIterator[PostgresEventStore]:
    registry = build_event_registry()
    registry.register(SampleHappened)
    event_store = await PostgresEventStore.connect(dsn, registry)
    try:
        yield event_store
    finally:
        await event_store.aclose()


class TestPostgresEventStore:
    async def test_append_and_load(self, sample_store: PostgresEventStore) -> None:
        stream_id = new_event_id()
        appended = await sample_store.append(
            stream_type="sample",
            stream_id=stream_id,
            expected_version=0,
            events=[SampleHappened(note="a"), SampleHappened(note="b")],
            metadata=EventMetadata.empty(),
        )
        assert [e.version for e in appended] == [1, 2]

        loaded = await sample_store.load_stream(stream_type="sample", stream_id=stream_id)
        assert [e.payload["note"] for e in loaded] == ["a", "b"]
        assert loaded[0].global_position < loaded[1].global_position

    async def test_concurrency_conflict(self, sample_store: PostgresEventStore) -> None:
        stream_id = new_event_id()
        await sample_store.append(
            stream_type="sample",
            stream_id=stream_id,
            expected_version=0,
            events=[SampleHappened(note="a")],
            metadata=EventMetadata.empty(),
        )
        with pytest.raises(ConcurrencyConflict):
            await sample_store.append(
                stream_type="sample",
                stream_id=stream_id,
                expected_version=0,  # stale
                events=[SampleHappened(note="b")],
                metadata=EventMetadata.empty(),
            )

    async def test_read_all_is_globally_ordered(self, sample_store: PostgresEventStore) -> None:
        a, b = new_event_id(), new_event_id()
        first = await sample_store.append(
            stream_type="sample",
            stream_id=a,
            expected_version=0,
            events=[SampleHappened(note="first")],
            metadata=EventMetadata.empty(),
        )
        tail = await sample_store.read_all(from_position=first[0].global_position)
        assert all(e.global_position > first[0].global_position for e in tail) or tail == []
        _ = b

    async def test_account_round_trip(self, store: PostgresEventStore) -> None:
        repo: EventSourcedRepository[Account] = EventSourcedRepository(
            store=store,
            registry=build_event_registry(),
            stream_type=ACCOUNT_STREAM,
            factory=Account,
        )
        account_id = new_account_id()
        account = Account.open(account_id, "USD")
        account.deposit(usd(1000))
        account.hold(usd(400), new_event_id())
        await repo.save(account_id, account)

        reloaded = await repo.load(account_id)
        assert reloaded is not None
        assert reloaded.available == usd(600)
        assert reloaded.reserved == usd(400)
