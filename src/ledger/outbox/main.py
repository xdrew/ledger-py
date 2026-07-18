"""``ledger-relay`` — run the outbox relay against Postgres.

Tails the event log from a durable checkpoint and publishes each event via
``pg_notify`` (at-least-once). Shares the event store's connection pool and shuts
down cleanly on SIGINT/SIGTERM (so ``docker stop`` drains without error).
"""

import asyncio
import logging
import signal

from ledger.config.settings import Settings, get_settings
from ledger.eventstore.factory import open_event_store
from ledger.eventstore.postgres import PostgresEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.observability.setup import configure_observability
from ledger.outbox.relay import OutboxRelay, PostgresNotifyPublisher, run_relay
from ledger.projections.pg_checkpoints import PostgresCheckpointStore

_log = logging.getLogger(__name__)


async def run_relay_process(settings: Settings) -> None:
    registry = build_event_registry()
    store = await open_event_store(settings, registry)  # ensures the schema (checkpoint table)
    if not isinstance(store, PostgresEventStore):
        raise RuntimeError("ledger-relay requires a Postgres event store")
    pool = store.pool  # reuse the store's pool for the checkpoint + publisher
    try:
        relay = OutboxRelay(
            store=store,
            checkpoints=PostgresCheckpointStore(pool, table="relay_checkpoints"),
            publisher=PostgresNotifyPublisher(pool),
        )
        task = asyncio.create_task(run_relay(relay))
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, task.cancel)
        try:
            await task
        except asyncio.CancelledError:
            _log.info("relay shutting down")
    finally:
        await store.aclose()


def main() -> None:
    settings = get_settings()
    configure_observability(settings)
    asyncio.run(run_relay_process(settings))


if __name__ == "__main__":
    main()
