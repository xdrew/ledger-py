"""``AggregateRoot`` — the event-sourcing base class.

State changes go through :meth:`_record`, which applies the event to in-memory
state *and* buffers it for persistence. Rehydration replays committed events
through the same :meth:`_apply`, so there is exactly one place that mutates
state. Generic over the concrete event union via PEP 695 syntax.
"""

from collections.abc import Iterable


class AggregateRoot[E]:
    """Base for event-sourced aggregates. ``E`` is the event union type."""

    def __init__(self) -> None:
        self._version: int = 0
        self._pending: list[E] = []

    @property
    def version(self) -> int:
        """Total number of events applied (history + uncommitted)."""
        return self._version

    @property
    def expected_version(self) -> int:
        """Version the backing stream should currently be at (excludes pending).

        This is what the event store checks for optimistic concurrency when the
        buffered events are appended.
        """
        return self._version - len(self._pending)

    @property
    def has_pending_events(self) -> bool:
        return bool(self._pending)

    def _apply(self, event: E) -> None:
        """Mutate state from a single event. Subclasses dispatch on the event
        type (typically with ``match``). Must be side-effect free.
        """
        raise NotImplementedError

    def _record(self, event: E) -> None:
        """Apply a new event and buffer it for persistence."""
        self._apply(event)
        self._version += 1
        self._pending.append(event)

    def pull_pending_events(self) -> list[E]:
        """Return and clear the buffered events (called by the repository)."""
        events = self._pending
        self._pending = []
        return events

    def load_from_history(self, events: Iterable[E]) -> None:
        """Rehydrate from committed events. No events are buffered."""
        for event in events:
            self._apply(event)
            self._version += 1
