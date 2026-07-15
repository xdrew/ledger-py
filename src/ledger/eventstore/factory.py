"""Event store construction.

For now this returns the in-memory store so the worker and API run end-to-end
without external infrastructure. The Postgres (asyncpg) implementation lands in
the infra phase and will be selected here from settings — the rest of the code
depends only on the ``EventStore`` protocol, so nothing else changes.
"""

import logging

from ledger.config.settings import Settings
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import EventStore

_log = logging.getLogger(__name__)


def create_event_store(settings: Settings, registry: EventRegistry) -> EventStore:
    # TODO(infra-phase): return PostgresEventStore(settings.database_url, registry).
    _log.warning("using in-memory event store (non-durable); Postgres store pending infra phase")
    return InMemoryEventStore(registry)
