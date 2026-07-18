"""Transfer domain events and failure taxonomy.

Temporal owns the *execution* of the transfer saga; these events are the
*audit/read* record of its milestones, appended to the event store by activities.
"""

from enum import StrEnum

from ledger.domain.shared.events import DomainEvent
from ledger.domain.shared.identifiers import AccountId, JournalEntryId, TransferId
from ledger.domain.shared.money import Money


class FailureReason(StrEnum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CONFLICT = "conflict"
    UNKNOWN_ACCOUNT = "unknown_account"
    ACCOUNT_NOT_ACTIVE = "account_not_active"
    CURRENCY_MISMATCH = "currency_mismatch"
    UNBALANCED = "unbalanced_entry"
    OTHER = "other"


class TransferInitiated(DomainEvent):
    source_account_id: AccountId
    destination_account_id: AccountId
    amount: Money
    # Intentional forward-scaffolding for the deferred "reversal of a completed
    # transfer" feature (see project.md → Deferred); unset until that lands.
    reversal_of: TransferId | None = None


class TransferHeld(DomainEvent):
    pass


class TransferPosted(DomainEvent):
    journal_entry_id: JournalEntryId


class TransferCompleted(DomainEvent):
    pass


class TransferFailed(DomainEvent):
    reason: FailureReason
    detail: str | None = None


class TransferParkedForReconciliation(DomainEvent):
    detail: str


class TransferReconciled(DomainEvent):
    """A parked transfer was resolved by an operator decision.

    ``resolution`` is the applied outcome (e.g. ``refunded``); the money movement
    that backs it (a refund credit to the source) is recorded on the account
    stream. A retried credit that succeeds records ``TransferCompleted`` instead.
    """

    resolution: str
    detail: str | None = None


type TransferEvent = (
    TransferInitiated
    | TransferHeld
    | TransferPosted
    | TransferCompleted
    | TransferFailed
    | TransferParkedForReconciliation
    | TransferReconciled
)

TRANSFER_STREAM = "transfer"

TRANSFER_EVENT_TYPES: tuple[type[DomainEvent], ...] = (
    TransferInitiated,
    TransferHeld,
    TransferPosted,
    TransferCompleted,
    TransferFailed,
    TransferParkedForReconciliation,
    TransferReconciled,
)
