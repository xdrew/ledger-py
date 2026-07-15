"""HTTP-level idempotency via the ``Idempotency-Key`` header.

An in-memory store keyed by (key, route) that replays the first response for a
repeated key. Transport-level dedup, complementary to the workflow-id dedup at
the Temporal layer. The Postgres-backed version (with TTL) lands in the infra
phase; the interface stays the same.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


class IdempotencyStore:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], StoredResponse] = {}

    def recall(self, key: str, route: str) -> StoredResponse | None:
        return self._entries.get((key, route))

    def remember(self, key: str, route: str, status_code: int, body: dict[str, Any]) -> None:
        self._entries.setdefault((key, route), StoredResponse(status_code, body))
