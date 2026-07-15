"""Generic event-sourced repository.

Loads an aggregate by replaying its stream, saves by appending buffered events
under the aggregate's expected version (optimistic concurrency). Works for any
aggregate; the concrete type is supplied via ``factory`` and ``stream_type``.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from ledger.domain.shared.aggregate import AggregateRoot
from ledger.eventstore.records import EventMetadata, StoredEvent
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import EventStore


class EventSourcedRepository[A: AggregateRoot[Any]]:
    def __init__(
        self,
        *,
        store: EventStore,
        registry: EventRegistry,
        stream_type: str,
        factory: Callable[[], A],
    ) -> None:
        self._store = store
        self._registry = registry
        self._stream_type = stream_type
        self._factory = factory

    async def load(self, aggregate_id: UUID) -> A | None:
        stored = await self._store.load_stream(
            stream_type=self._stream_type, stream_id=aggregate_id
        )
        if not stored:
            return None
        events = [
            self._registry.deserialize(
                event_type=record.event_type,
                schema_version=record.schema_version,
                payload=record.payload,
            )
            for record in stored
        ]
        aggregate = self._factory()
        aggregate.load_from_history(events)
        return aggregate

    async def save(
        self,
        aggregate_id: UUID,
        aggregate: A,
        metadata: EventMetadata | None = None,
    ) -> list[StoredEvent]:
        expected_version = aggregate.expected_version
        pending = aggregate.pull_pending_events()
        if not pending:
            return []
        return await self._store.append(
            stream_type=self._stream_type,
            stream_id=aggregate_id,
            expected_version=expected_version,
            events=pending,
            metadata=metadata or EventMetadata.empty(),
        )
