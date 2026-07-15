"""Wiring: build the aggregate repositories the activities depend on."""

from dataclasses import dataclass

from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.ledger.events import JOURNAL_STREAM
from ledger.domain.ledger.journal_entry import JournalEntry
from ledger.domain.transfers.events import TRANSFER_STREAM
from ledger.domain.transfers.transfer import Transfer
from ledger.eventstore.repository import EventSourcedRepository
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import EventStore


@dataclass(frozen=True, slots=True)
class LedgerRepositories:
    accounts: EventSourcedRepository[Account]
    journals: EventSourcedRepository[JournalEntry]
    transfers: EventSourcedRepository[Transfer]


def build_repositories(store: EventStore, registry: EventRegistry) -> LedgerRepositories:
    return LedgerRepositories(
        accounts=EventSourcedRepository(
            store=store,
            registry=registry,
            stream_type=ACCOUNT_STREAM,
            factory=Account,
        ),
        journals=EventSourcedRepository(
            store=store,
            registry=registry,
            stream_type=JOURNAL_STREAM,
            factory=JournalEntry,
        ),
        transfers=EventSourcedRepository(
            store=store,
            registry=registry,
            stream_type=TRANSFER_STREAM,
            factory=Transfer,
        ),
    )
