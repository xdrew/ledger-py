"""Central event registry wiring.

One place that knows every persisted event type. Extend this as bounded contexts
add events (transfers arrive in the Temporal phase).
"""

from ledger.domain.accounts.events import ACCOUNT_EVENT_TYPES
from ledger.domain.ledger.events import JOURNAL_EVENT_TYPES
from ledger.eventstore.serialization import EventRegistry


def build_event_registry() -> EventRegistry:
    registry = EventRegistry()
    for event_cls in (*ACCOUNT_EVENT_TYPES, *JOURNAL_EVENT_TYPES):
        registry.register(event_cls)
    return registry
