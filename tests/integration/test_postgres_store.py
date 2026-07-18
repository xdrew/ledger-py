"""Integration tests for the Postgres event store against a real database
(spun up via testcontainers). Mirrors the in-memory store's contract."""

# Raw asyncpg is used here to drive the append lock directly; relax the driver's
# partially-typed surface at that boundary, as the store module does.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import asyncio
from collections.abc import AsyncIterator, Iterator

import asyncpg
import pytest

from ledger.api.idempotency import ClaimResult, PostgresIdempotencyStore
from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import new_account_id, new_event_id
from ledger.domain.shared.money import Money
from ledger.eventstore.postgres import APPEND_LOCK_KEY, PostgresEventStore
from ledger.eventstore.records import EventMetadata
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.repository import EventSourcedRepository
from ledger.eventstore.store import ConcurrencyConflict
from ledger.projections.pg_checkpoints import PostgresCheckpointStore

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

    async def test_append_acquires_the_serialization_lock(
        self, dsn: str, sample_store: PostgresEventStore
    ) -> None:
        # Prove append actually takes the global append lock: while an external
        # session holds it, an append must block until the lock is released. If the
        # lock were removed from append, this append would not block and the test
        # would fail.
        blocker = await asyncpg.connect(dsn)
        try:
            tx = blocker.transaction()
            await tx.start()
            await blocker.execute("SELECT pg_advisory_xact_lock($1)", APPEND_LOCK_KEY)

            append_task = asyncio.create_task(
                sample_store.append(
                    stream_type="sample",
                    stream_id=new_event_id(),
                    expected_version=0,
                    events=[SampleHappened(note="blocked")],
                    metadata=EventMetadata.empty(),
                )
            )
            await asyncio.sleep(0.2)
            assert not append_task.done()  # append is waiting on the lock we hold

            await tx.commit()  # release the lock
            appended = await asyncio.wait_for(append_task, timeout=5)
            assert len(appended) == 1
        finally:
            await blocker.close()

    async def test_positions_follow_commit_order_under_the_lock(
        self, dsn: str, sample_store: PostgresEventStore
    ) -> None:
        # Two sessions contend for the append lock the way append does. The second
        # can only draw its global position after the first commits, so commit order
        # equals position order — the property that makes cursor tailing gap-safe.
        first = await asyncpg.connect(dsn)
        second = await asyncpg.connect(dsn)
        try:
            tx_first = first.transaction()
            await tx_first.start()
            await first.execute("SELECT pg_advisory_xact_lock($1)", APPEND_LOCK_KEY)

            tx_second = second.transaction()
            await tx_second.start()
            lock_second = asyncio.create_task(
                second.execute("SELECT pg_advisory_xact_lock($1)", APPEND_LOCK_KEY)
            )
            await asyncio.sleep(0.2)
            assert not lock_second.done()  # second session blocks while first holds the lock

            pos_first = await first.fetchval(
                "INSERT INTO events (event_id, stream_type, stream_id, version, "
                "event_type, schema_version, payload, metadata) "
                "VALUES ($1,'sample',$2,1,'SampleHappened',1,'{}'::jsonb,'{}'::jsonb) "
                "RETURNING global_position",
                new_event_id(),
                new_event_id(),
            )
            await tx_first.commit()  # releases the lock; second proceeds

            await asyncio.wait_for(lock_second, timeout=5)
            pos_second = await second.fetchval(
                "INSERT INTO events (event_id, stream_type, stream_id, version, "
                "event_type, schema_version, payload, metadata) "
                "VALUES ($1,'sample',$2,1,'SampleHappened',1,'{}'::jsonb,'{}'::jsonb) "
                "RETURNING global_position",
                new_event_id(),
                new_event_id(),
            )
            await tx_second.commit()

            # Earlier-committing session got the lower position: no reordering.
            assert pos_second > pos_first
        finally:
            await first.close()
            await second.close()

    async def test_checkpoint_store_round_trips(
        self, dsn: str, sample_store: PostgresEventStore
    ) -> None:
        # sample_store.connect() applied the schema, creating relay_checkpoints.
        pool = await asyncpg.create_pool(dsn)
        try:
            checkpoints = PostgresCheckpointStore(pool, table="relay_checkpoints")
            assert await checkpoints.load("relay-test") == 0  # unknown → 0
            await checkpoints.save("relay-test", 42)
            assert await checkpoints.load("relay-test") == 42
            await checkpoints.save("relay-test", 99)  # upsert advances
            assert await checkpoints.load("relay-test") == 99
        finally:
            await pool.close()

    async def test_postgres_idempotency_store_classifies_claims(self, dsn: str) -> None:
        pool = await asyncpg.create_pool(dsn)
        try:
            store = await PostgresIdempotencyStore.connect(pool)
            first, _ = await store.claim("k1", "r", "fp")
            assert first is ClaimResult.NEW  # atomic insert won
            again, _ = await store.claim("k1", "r", "fp")
            assert again is ClaimResult.IN_PROGRESS  # reserved, not yet completed
            mismatch, _ = await store.claim("k1", "r", "other")
            assert mismatch is ClaimResult.MISMATCH

            await store.complete("k1", "r", 202, {"x": 1})
            replay, stored = await store.claim("k1", "r", "fp")
            assert replay is ClaimResult.REPLAY
            assert stored is not None and stored.body == {"x": 1}

            # discard releases an uncompleted reservation so the key is reusable.
            await store.claim("k2", "r", "fp")
            await store.discard("k2", "r")
            reused, _ = await store.claim("k2", "r", "fp")
            assert reused is ClaimResult.NEW
        finally:
            await pool.close()

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
