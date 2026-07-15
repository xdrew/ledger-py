"""In-memory :class:`EventStore` for unit tests and fast domain iteration.

Semantically identical to the Postgres store (same optimistic-concurrency
guard, same global ordering) but with no I/O.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import new_event_id
from ledger.eventstore.records import EventMetadata, StoredEvent
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import ConcurrencyConflict


class InMemoryEventStore:
    """A list-backed append-only log honoring per-stream versioning."""

    def __init__(self, registry: EventRegistry) -> None:
        self._registry = registry
        self._events: list[StoredEvent] = []

    def _current_version(self, stream_type: str, stream_id: UUID) -> int:
        return max(
            (
                event.version
                for event in self._events
                if event.stream_type == stream_type and event.stream_id == stream_id
            ),
            default=0,
        )

    async def append(
        self,
        *,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[DomainEvent],
        metadata: EventMetadata,
    ) -> list[StoredEvent]:
        actual = self._current_version(stream_type, stream_id)
        if actual != expected_version:
            raise ConcurrencyConflict(stream_type, stream_id, expected_version, actual)

        appended: list[StoredEvent] = []
        for offset, event in enumerate(events, start=1):
            stored = StoredEvent(
                global_position=len(self._events) + 1,
                event_id=new_event_id(),
                stream_type=stream_type,
                stream_id=stream_id,
                version=expected_version + offset,
                event_type=self._registry.name_for(event),
                schema_version=self._registry.schema_version_for(event),
                payload=self._registry.serialize(event),
                metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
            self._events.append(stored)
            appended.append(stored)
        return appended

    async def load_stream(self, *, stream_type: str, stream_id: UUID) -> list[StoredEvent]:
        return [
            event
            for event in self._events
            if event.stream_type == stream_type and event.stream_id == stream_id
        ]

    async def read_all(self, *, from_position: int = 0, limit: int = 500) -> list[StoredEvent]:
        matching = [e for e in self._events if e.global_position > from_position]
        return matching[:limit]
