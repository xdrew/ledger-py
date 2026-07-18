"""Durable checkpoint store (asyncpg) for projections and the outbox relay.

Implements the ``CheckpointStore`` protocol with an upsert on a checkpoints table
(``relay_checkpoints`` or ``projection_checkpoints``, both created by the schema).
"""

# asyncpg exposes a partially-typed surface; relax at the driver boundary.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import asyncpg


class PostgresCheckpointStore:
    """A named checkpoint persisted in a Postgres table (``name`` → ``position``)."""

    def __init__(self, pool: asyncpg.Pool, table: str = "relay_checkpoints") -> None:
        if not table.isidentifier():
            raise ValueError(f"unsafe checkpoint table name: {table!r}")
        self._pool = pool
        self._table = table

    async def load(self, name: str) -> int:
        async with self._pool.acquire() as conn:
            row = await conn.fetchval(
                f"SELECT position FROM {self._table} WHERE name = $1",
                name,
            )
        return int(row) if row is not None else 0

    async def save(self, name: str, position: int) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"INSERT INTO {self._table} (name, position) VALUES ($1, $2) "
                "ON CONFLICT (name) DO UPDATE SET position = EXCLUDED.position",
                name,
                position,
            )
