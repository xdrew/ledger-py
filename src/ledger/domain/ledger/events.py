"""Ledger domain events."""

from ledger.domain.ledger.leg import Leg
from ledger.domain.shared.events import DomainEvent


class JournalEntryPosted(DomainEvent):
    legs: tuple[Leg, ...]
    reference: str | None = None


type JournalEvent = JournalEntryPosted

JOURNAL_STREAM = "journal"

JOURNAL_EVENT_TYPES: tuple[type[DomainEvent], ...] = (JournalEntryPosted,)
