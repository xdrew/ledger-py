"""Envelope records for stored events.

These wrap a domain event with the persistence concerns the domain does not
carry: global position, per-stream version, and correlation/causation metadata
for the audit trail and distributed tracing.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class EventMetadata:
    """Cross-cutting envelope metadata threaded through the event log."""

    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    traceparent: str | None = None

    @classmethod
    def empty(cls) -> EventMetadata:
        return cls()


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """A domain event as persisted: envelope + serialized payload."""

    global_position: int
    event_id: UUID
    stream_type: str
    stream_id: UUID
    version: int
    event_type: str
    schema_version: int
    payload: dict[str, Any]
    metadata: EventMetadata
    occurred_at: datetime
