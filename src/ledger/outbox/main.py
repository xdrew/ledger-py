"""``ledger-relay`` — run the outbox relay against Postgres.

Tails the event log from a durable checkpoint and publishes each event via
``pg_notify`` (at-least-once). Runs until interrupted.
"""

# asyncpg's create_pool surface is partially typed; relax at the driver boundary.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import asyncio
import logging

import asyncpg

from ledger.config.settings import Settings, get_settings
from ledger.eventstore.factory import open_event_store
from ledger.eventstore.registry import build_event_registry
from ledger.observability.setup import configure_observability
from ledger.outbox.relay import OutboxRelay, PostgresNotifyPublisher, run_relay
from ledger.projections.pg_checkpoints import PostgresCheckpointStore

_log = logging.getLogger(__name__)


async def run_relay_process(settings: Settings) -> None:
    registry = build_event_registry()
    store = await open_event_store(settings, registry)  # ensures the schema (checkpoint table)
    pool = await asyncpg.create_pool(settings.database_url)
    try:
        relay = OutboxRelay(
            store=store,
            checkpoints=PostgresCheckpointStore(pool, table="relay_checkpoints"),
            publisher=PostgresNotifyPublisher(pool),
        )
        await run_relay(relay)
    finally:
        await pool.close()
        close = getattr(store, "aclose", None)
        if close is not None:
            await close()


def main() -> None:
    settings = get_settings()
    configure_observability(settings)
    asyncio.run(run_relay_process(settings))


if __name__ == "__main__":
    main()
