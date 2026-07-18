"""HTTP-level idempotency via the ``Idempotency-Key`` header.

A store keyed by ``(key, route)`` that claims a key atomically before any work,
records a fingerprint of the request, and replays the first response for a matching
repeat. Two interchangeable implementations behind the async :class:`IdempotencyStore`
protocol: an in-memory double for tests and single-process runs, and a durable
Postgres implementation for shared, multi-worker deployments.

The claim is race-safe: the first caller reserves the key before doing side-effecting
work, and a concurrent second caller sees ``IN_PROGRESS`` (in-memory: atomic under the
event loop; Postgres: atomic via ``INSERT ... ON CONFLICT DO NOTHING``).
"""

# asyncpg exposes a partially-typed surface; relax at the driver boundary.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import json
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Protocol

import asyncpg


class ClaimResult(Enum):
    NEW = auto()  # caller reserved the key; must do the work then call complete()
    IN_PROGRESS = auto()  # a concurrent request holds the claim; reject as duplicate
    MISMATCH = auto()  # key reused with a different request fingerprint
    REPLAY = auto()  # key already completed; return the stored response


@dataclass(frozen=True, slots=True)
class StoredResponse:
    status_code: int
    body: dict[str, Any]


class IdempotencyStore(Protocol):
    async def claim(
        self, key: str, route: str, fingerprint: str
    ) -> tuple[ClaimResult, StoredResponse | None]: ...

    async def complete(
        self, key: str, route: str, status_code: int, body: dict[str, Any]
    ) -> None: ...

    async def discard(self, key: str, route: str) -> None: ...


@dataclass
class _Entry:
    fingerprint: str
    response: StoredResponse | None = None


class InMemoryIdempotencyStore:
    """Per-process store. ``claim`` performs no ``await`` — atomic under the loop."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], _Entry] = {}

    async def claim(
        self, key: str, route: str, fingerprint: str
    ) -> tuple[ClaimResult, StoredResponse | None]:
        entry = self._entries.get((key, route))
        if entry is None:
            self._entries[(key, route)] = _Entry(fingerprint=fingerprint)
            return ClaimResult.NEW, None
        if entry.fingerprint != fingerprint:
            return ClaimResult.MISMATCH, None
        if entry.response is None:
            return ClaimResult.IN_PROGRESS, None
        return ClaimResult.REPLAY, entry.response

    async def complete(self, key: str, route: str, status_code: int, body: dict[str, Any]) -> None:
        entry = self._entries.get((key, route))
        if entry is not None:
            entry.response = StoredResponse(status_code, body)

    async def discard(self, key: str, route: str) -> None:
        entry = self._entries.get((key, route))
        if entry is not None and entry.response is None:
            del self._entries[(key, route)]


IDEMPOTENCY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key          TEXT        NOT NULL,
    route        TEXT        NOT NULL,
    fingerprint  TEXT        NOT NULL,
    status_code  INTEGER,
    body         JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (key, route)
);
"""


class PostgresIdempotencyStore:
    """Durable, shared idempotency store. Atomic claim via ``ON CONFLICT DO NOTHING``."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(cls, pool: asyncpg.Pool) -> PostgresIdempotencyStore:
        async with pool.acquire() as conn:
            await conn.execute(IDEMPOTENCY_SCHEMA_SQL)
        return cls(pool)

    async def claim(
        self, key: str, route: str, fingerprint: str
    ) -> tuple[ClaimResult, StoredResponse | None]:
        async with self._pool.acquire() as conn:
            # Atomic reservation: a returned row means we inserted (we are first).
            inserted = await conn.fetchval(
                "INSERT INTO idempotency_keys (key, route, fingerprint) VALUES ($1, $2, $3) "
                "ON CONFLICT (key, route) DO NOTHING RETURNING key",
                key,
                route,
                fingerprint,
            )
            if inserted is not None:
                return ClaimResult.NEW, None
            row = await conn.fetchrow(
                "SELECT fingerprint, status_code, body FROM idempotency_keys "
                "WHERE key = $1 AND route = $2",
                key,
                route,
            )
        if row is None or row["fingerprint"] != fingerprint:
            return ClaimResult.MISMATCH, None
        if row["status_code"] is None:
            return ClaimResult.IN_PROGRESS, None
        body = row["body"]
        parsed: dict[str, Any] = json.loads(body) if isinstance(body, str) else body
        return ClaimResult.REPLAY, StoredResponse(int(row["status_code"]), parsed)

    async def complete(self, key: str, route: str, status_code: int, body: dict[str, Any]) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE idempotency_keys SET status_code = $3, body = $4::jsonb "
                "WHERE key = $1 AND route = $2",
                key,
                route,
                status_code,
                json.dumps(body),
            )

    async def discard(self, key: str, route: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM idempotency_keys "
                "WHERE key = $1 AND route = $2 AND status_code IS NULL",
                key,
                route,
            )
