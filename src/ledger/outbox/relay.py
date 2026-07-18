"""Outbox relay — republishes the event log to external consumers.

Tails the global event stream from a durable checkpoint and hands each event to
a publisher, then advances the checkpoint (at-least-once, so publishers must be
idempotent downstream). This is the *external* delivery path; internal saga
reliability is Temporal's job, so the relay is not on the critical path.
"""

# asyncpg's call surface is only partially typed; relax at that boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio
import json
import logging
from typing import Protocol

import asyncpg

from ledger.eventstore.records import StoredEvent
from ledger.eventstore.store import EventStore
from ledger.projections.runner import CheckpointStore

_log = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish(self, event: StoredEvent) -> None: ...


class LoggingEventPublisher:
    """Default publisher — structured log line per event (a stand-in sink)."""

    async def publish(self, event: StoredEvent) -> None:
        _log.info(
            "outbox.publish",
            extra={
                "global_position": event.global_position,
                "stream_type": event.stream_type,
                "event_type": event.event_type,
            },
        )


class PostgresNotifyPublisher:
    """Publishes via Postgres ``pg_notify`` on a channel (LISTEN/NOTIFY fan-out)."""

    def __init__(self, pool: asyncpg.Pool, channel: str = "ledger_events") -> None:
        self._pool = pool
        self._channel = channel

    async def publish(self, event: StoredEvent) -> None:
        payload = json.dumps(
            {
                "global_position": event.global_position,
                "stream_type": event.stream_type,
                "stream_id": str(event.stream_id),
                "event_type": event.event_type,
            }
        )
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT pg_notify($1, $2)", self._channel, payload)


class OutboxRelay:
    def __init__(
        self,
        *,
        store: EventStore,
        checkpoints: CheckpointStore,
        publisher: EventPublisher,
        name: str = "outbox",
        batch_size: int = 500,
    ) -> None:
        self._store = store
        self._checkpoints = checkpoints
        self._publisher = publisher
        self._name = name
        self._batch_size = batch_size

    async def run_once(self) -> int:
        position = await self._checkpoints.load(self._name)
        batch = await self._store.read_all(from_position=position, limit=self._batch_size)
        for event in batch:
            await self._publisher.publish(event)
            position = event.global_position
        if batch:
            await self._checkpoints.save(self._name, position)
        return len(batch)

    async def drain(self) -> int:
        total = 0
        while (handled := await self.run_once()) > 0:
            total += handled
        return total


async def run_relay(relay: OutboxRelay, *, poll_seconds: float = 1.0) -> None:
    """Continuously drain ``relay``, waiting between passes, until cancelled.

    Publishes new events as they arrive; exits cleanly on cancellation.
    """
    _log.info("outbox relay started")
    try:
        while True:
            await relay.drain()
            await asyncio.sleep(poll_seconds)
    except asyncio.CancelledError:
        _log.info("outbox relay stopped")
        raise
