"""Typed identifiers.

PEP 695 ``type`` aliases give readable, self-documenting signatures while
staying structurally ``UUID`` (so pydantic/JSON/asyncpg handle them for free).
All new ids are time-ordered UUIDv7 from the stdlib (``uuid.uuid7()``, new in
3.14) — they sort by creation time, which keeps event streams and indexes tidy.
"""

import uuid

type AccountId = uuid.UUID
type TransferId = uuid.UUID
type JournalEntryId = uuid.UUID
type EventId = uuid.UUID
type CorrelationId = uuid.UUID
type CausationId = uuid.UUID


def new_account_id() -> AccountId:
    return uuid.uuid7()


def new_transfer_id() -> TransferId:
    return uuid.uuid7()


def new_journal_entry_id() -> JournalEntryId:
    return uuid.uuid7()


def new_event_id() -> EventId:
    return uuid.uuid7()


def new_correlation_id() -> CorrelationId:
    return uuid.uuid7()
