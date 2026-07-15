"""Projection plumbing: projectors, checkpoints, and a batch runner.

The runner reads the global event log from a stored checkpoint, feeds each event
to every projector, then advances the checkpoint — at-least-once, so projectors
must be idempotent under replay.
"""

from collections.abc import Sequence
from typing import Protocol

from ledger.eventstore.records import StoredEvent
from ledger.eventstore.store import EventStore


class Projector(Protocol):
    async def project(self, event: StoredEvent) -> None: ...


class CheckpointStore(Protocol):
    async def load(self, name: str) -> int: ...
    async def save(self, name: str, position: int) -> None: ...


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._positions: dict[str, int] = {}

    async def load(self, name: str) -> int:
        return self._positions.get(name, 0)

    async def save(self, name: str, position: int) -> None:
        self._positions[name] = position


class ProjectionRunner:
    def __init__(
        self,
        *,
        store: EventStore,
        checkpoints: CheckpointStore,
        name: str,
        projectors: Sequence[Projector],
        batch_size: int = 500,
    ) -> None:
        self._store = store
        self._checkpoints = checkpoints
        self._name = name
        self._projectors = projectors
        self._batch_size = batch_size

    async def run_once(self) -> int:
        """Process one batch. Returns the number of events handled."""
        position = await self._checkpoints.load(self._name)
        batch = await self._store.read_all(from_position=position, limit=self._batch_size)
        for event in batch:
            for projector in self._projectors:
                await projector.project(event)
            position = event.global_position
        if batch:
            await self._checkpoints.save(self._name, position)
        return len(batch)

    async def drain(self) -> int:
        """Run batches until the log is fully caught up. Returns total handled."""
        total = 0
        while (handled := await self.run_once()) > 0:
            total += handled
        return total
