"""Event store interface.

The store is an append-only log with per-stream optimistic concurrency. It is a
structural ``Protocol`` so the in-memory (test) and Postgres (production)
implementations are interchangeable without a base class.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ledger.domain.shared.events import DomainEvent
from ledger.eventstore.records import EventMetadata, StoredEvent


class ConcurrencyConflict(Exception):
    """Raised when a stream's actual version differs from the expected version.

    Surfaces the optimistic-concurrency guard (``UNIQUE(stream_type, stream_id,
    version)`` in Postgres) as a domain-meaningful signal the saga can retry on.
    """

    def __init__(self, stream_type: str, stream_id: UUID, expected: int, actual: int) -> None:
        super().__init__(
            f"concurrency conflict on {stream_type}:{stream_id} — "
            f"expected v{expected}, actual v{actual}"
        )
        self.stream_type = stream_type
        self.stream_id = stream_id
        self.expected = expected
        self.actual = actual


class EventStore(Protocol):
    """Append-only event log."""

    async def append(
        self,
        *,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[DomainEvent],
        metadata: EventMetadata,
    ) -> list[StoredEvent]:
        """Append ``events`` to a stream.

        Raises :class:`ConcurrencyConflict` if the stream is not at
        ``expected_version``. Returns the persisted envelopes in order.
        """
        ...

    async def load_stream(self, *, stream_type: str, stream_id: UUID) -> list[StoredEvent]:
        """Return all events of one stream, ordered by version."""
        ...

    async def read_all(self, *, from_position: int = 0, limit: int = 500) -> list[StoredEvent]:
        """Return events across all streams with ``global_position >
        from_position``, ordered by global position. Drives projections and the
        outbox relay.
        """
        ...
