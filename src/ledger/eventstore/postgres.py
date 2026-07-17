"""Postgres (asyncpg) implementation of the event store.

Same contract as the in-memory store; the ``UNIQUE(stream_type, stream_id,
version)`` constraint enforces optimistic concurrency, surfaced as
``ConcurrencyConflict``.
"""

# asyncpg exposes a partially-typed surface; relax unknown-type noise at the
# driver boundary (our own logic stays fully typed).
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import new_event_id
from ledger.eventstore.records import EventMetadata, StoredEvent
from ledger.eventstore.schema import SCHEMA_SQL
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import ConcurrencyConflict

_INSERT = """
INSERT INTO events (
    event_id, stream_type, stream_id, version,
    event_type, schema_version, payload, metadata
) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)
RETURNING global_position, occurred_at
"""

# Global advisory-lock key, held for the whole append transaction so that
# `global_position` (an IDENTITY sequence value assigned at INSERT time) is
# handed out in commit order. Without it, a lower position can become visible
# *after* a higher one was already consumed by a cursor tailer (projections /
# outbox), silently skipping the lower-position event. Serializing appends makes
# committed positions strictly increasing for consumers — no reordering, so a
# cursor tail can never skip a committed event. Holes left by rolled-back appends
# are harmless (a consumer just finds nothing at that number). The key is a fixed
# app-namespaced constant so it cannot collide with locks taken elsewhere.
# See changes/fix-eventstore-gapless-tailing for the full rationale.
APPEND_LOCK_KEY = 0x1ED6E12A11_00_0001


def _metadata_to_json(metadata: EventMetadata) -> str:
    return json.dumps(
        {
            "correlation_id": str(metadata.correlation_id) if metadata.correlation_id else None,
            "causation_id": str(metadata.causation_id) if metadata.causation_id else None,
            "traceparent": metadata.traceparent,
        }
    )


def _metadata_from_json(raw: str | None) -> EventMetadata:
    if not raw:
        return EventMetadata.empty()
    data: dict[str, Any] = json.loads(raw)
    correlation = data.get("correlation_id")
    causation = data.get("causation_id")
    return EventMetadata(
        correlation_id=UUID(correlation) if correlation else None,
        causation_id=UUID(causation) if causation else None,
        traceparent=data.get("traceparent"),
    )


class PostgresEventStore:
    def __init__(self, pool: asyncpg.Pool, registry: EventRegistry) -> None:
        self._pool = pool
        self._registry = registry

    @classmethod
    async def connect(
        cls,
        dsn: str,
        registry: EventRegistry,
        *,
        min_size: int = 1,
        max_size: int = 10,
    ) -> PostgresEventStore:
        pool = await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        store = cls(pool, registry)
        await store.ensure_schema()
        return store

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)

    async def aclose(self) -> None:
        await self._pool.close()

    async def append(
        self,
        *,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[DomainEvent],
        metadata: EventMetadata,
    ) -> list[StoredEvent]:
        metadata_json = _metadata_to_json(metadata)
        appended: list[StoredEvent] = []
        async with self._pool.acquire() as conn, conn.transaction():
            # Serialize position assignment with a txn-scoped advisory lock so
            # `global_position` order equals commit order (see APPEND_LOCK_KEY).
            # Released automatically at COMMIT/ROLLBACK.
            await conn.execute("SELECT pg_advisory_xact_lock($1)", APPEND_LOCK_KEY)
            current = await conn.fetchval(
                "SELECT COALESCE(MAX(version), 0) FROM events "
                "WHERE stream_type = $1 AND stream_id = $2",
                stream_type,
                stream_id,
            )
            if current != expected_version:
                raise ConcurrencyConflict(stream_type, stream_id, expected_version, int(current))
            for offset, event in enumerate(events, start=1):
                version = expected_version + offset
                event_id = new_event_id()
                event_type = self._registry.name_for(event)
                schema_version = self._registry.schema_version_for(event)
                payload = self._registry.serialize(event)
                try:
                    row = await conn.fetchrow(
                        _INSERT,
                        event_id,
                        stream_type,
                        stream_id,
                        version,
                        event_type,
                        schema_version,
                        json.dumps(payload),
                        metadata_json,
                    )
                except asyncpg.UniqueViolationError as err:
                    raise ConcurrencyConflict(
                        stream_type, stream_id, expected_version, version
                    ) from err
                appended.append(
                    StoredEvent(
                        global_position=row["global_position"],
                        event_id=event_id,
                        stream_type=stream_type,
                        stream_id=stream_id,
                        version=version,
                        event_type=event_type,
                        schema_version=schema_version,
                        payload=payload,
                        metadata=metadata,
                        occurred_at=row["occurred_at"],
                    )
                )
        return appended

    async def load_stream(self, *, stream_type: str, stream_id: UUID) -> list[StoredEvent]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE stream_type = $1 AND stream_id = $2 ORDER BY version",
                stream_type,
                stream_id,
            )
        return [self._to_stored(row) for row in rows]

    async def read_all(self, *, from_position: int = 0, limit: int = 500) -> list[StoredEvent]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE global_position > $1 ORDER BY global_position LIMIT $2",
                from_position,
                limit,
            )
        return [self._to_stored(row) for row in rows]

    def _to_stored(self, row: asyncpg.Record) -> StoredEvent:
        raw_payload = row["payload"]
        payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        return StoredEvent(
            global_position=row["global_position"],
            event_id=row["event_id"],
            stream_type=row["stream_type"],
            stream_id=row["stream_id"],
            version=row["version"],
            event_type=row["event_type"],
            schema_version=row["schema_version"],
            payload=payload,
            metadata=_metadata_from_json(row["metadata"]),
            occurred_at=row["occurred_at"],
        )
