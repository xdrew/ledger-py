"""Event store selection.

Chooses the Postgres store when a real database URL is configured, else the
in-memory store (tests, local smoke). Everything else depends only on the
``EventStore`` protocol.
"""

import logging

from ledger.config.settings import Settings
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.postgres import PostgresEventStore
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import EventStore

_log = logging.getLogger(__name__)


async def open_event_store(settings: Settings, registry: EventRegistry) -> EventStore:
    dsn = settings.database_url
    if dsn.startswith(("postgresql://", "postgres://")):
        _log.info("connecting Postgres event store")
        return await PostgresEventStore.connect(
            dsn,
            registry,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
        )
    _log.warning("using in-memory event store (non-durable)")
    return InMemoryEventStore(registry)
