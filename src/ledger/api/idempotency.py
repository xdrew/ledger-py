"""HTTP-level idempotency via the ``Idempotency-Key`` header.

An in-memory store keyed by (key, route) that claims a key atomically before any
work is done, records a fingerprint of the request, and replays the first
response for a matching repeat. Transport-level dedup, complementary to the
workflow-id dedup at the Temporal layer.

The claim is race-safe within a process: :meth:`IdempotencyStore.claim` performs
no ``await``, so under the single-threaded event loop it is atomic with respect to
other in-flight requests — the first caller reserves the key before yielding at
its first ``await``, and a concurrent second caller sees ``IN_PROGRESS``. The
Postgres-backed, TTL'd version (with the same claim semantics via
``INSERT ... ON CONFLICT DO NOTHING`` plus a fingerprint column) is a drop-in
later; the interface stays the same.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class ClaimResult(Enum):
    NEW = auto()  # caller reserved the key; must do the work then call complete()
    IN_PROGRESS = auto()  # a concurrent request holds the claim; reject as duplicate
    MISMATCH = auto()  # key reused with a different request fingerprint
    REPLAY = auto()  # key already completed; return the stored response


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


@dataclass
class _Entry:
    fingerprint: str
    response: StoredResponse | None = None


class IdempotencyStore:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], _Entry] = {}

    def claim(
        self, key: str, route: str, fingerprint: str
    ) -> tuple[ClaimResult, StoredResponse | None]:
        """Atomically reserve ``key`` for ``route`` or classify the repeat.

        Performs no ``await`` — atomic under the event loop.
        """
        entry = self._entries.get((key, route))
        if entry is None:
            self._entries[(key, route)] = _Entry(fingerprint=fingerprint)
            return ClaimResult.NEW, None
        if entry.fingerprint != fingerprint:
            return ClaimResult.MISMATCH, None
        if entry.response is None:
            return ClaimResult.IN_PROGRESS, None
        return ClaimResult.REPLAY, entry.response

    def complete(self, key: str, route: str, status_code: int, body: dict[str, Any]) -> None:
        """Record the response for a previously claimed key."""
        entry = self._entries.get((key, route))
        if entry is not None:
            entry.response = StoredResponse(status_code, body)

    def discard(self, key: str, route: str) -> None:
        """Release a reservation whose work failed, so the key can be retried."""
        entry = self._entries.get((key, route))
        if entry is not None and entry.response is None:
            del self._entries[(key, route)]
