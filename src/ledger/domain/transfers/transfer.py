"""The ``Transfer`` aggregate — the saga's state machine and audit stream.

Temporal drives the process; this aggregate records each milestone and enforces
legal transitions, so the persisted stream is a faithful, queryable history:

    Initiated -> Held -> Posted -> Completed
                                \\-> NeedsReconciliation   (credit failed post-debit)
                                        |-> Reconciled     (operator refunded the source)
                                        \\-> Completed     (operator retried credit; it landed)
    (Initiated|Held|Posted) -> Failed                     (compensated, no money moved)
"""

from enum import StrEnum
from typing import Self

from ledger.domain.shared.aggregate import AggregateRoot
from ledger.domain.shared.errors import InvalidTransition, SameAccountTransfer
from ledger.domain.shared.identifiers import AccountId, JournalEntryId, TransferId
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import (
    FailureReason,
    TransferCompleted,
    TransferEvent,
    TransferFailed,
    TransferHeld,
    TransferInitiated,
    TransferParkedForReconciliation,
    TransferPosted,
    TransferReconciled,
)


class TransferStatus(StrEnum):
    INITIATED = "initiated"
    HELD = "held"
    POSTED = "posted"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_RECONCILIATION = "needs_reconciliation"
    RECONCILED = "reconciled"


_NON_TERMINAL = frozenset({TransferStatus.INITIATED, TransferStatus.HELD, TransferStatus.POSTED})


class Transfer(AggregateRoot[TransferEvent]):
    def __init__(self) -> None:
        super().__init__()
        self.transfer_id: TransferId | None = None
        self.source_account_id: AccountId | None = None
        self.destination_account_id: AccountId | None = None
        self.amount: Money | None = None
        self.status: TransferStatus = TransferStatus.INITIATED
        self.journal_entry_id: JournalEntryId | None = None
        self.failure_reason: FailureReason | None = None
        self.reversal_of: TransferId | None = None

    @classmethod
    def initiate(
        cls,
        transfer_id: TransferId,
        source_account_id: AccountId,
        destination_account_id: AccountId,
        amount: Money,
        reversal_of: TransferId | None = None,
    ) -> Self:
        amount.assert_positive()
        if source_account_id == destination_account_id:
            raise SameAccountTransfer("source and destination must be different accounts")
        transfer = cls()
        transfer.transfer_id = transfer_id
        transfer._record(
            TransferInitiated(
                source_account_id=source_account_id,
                destination_account_id=destination_account_id,
                amount=amount,
                reversal_of=reversal_of,
            )
        )
        return transfer

    def mark_held(self) -> None:
        self._assert_status(TransferStatus.INITIATED)
        self._record(TransferHeld())

    def mark_posted(self, journal_entry_id: JournalEntryId) -> None:
        self._assert_status(TransferStatus.HELD)
        self._record(TransferPosted(journal_entry_id=journal_entry_id))

    def complete(self) -> None:
        # Reachable from Posted (happy path) or from NeedsReconciliation when an
        # operator's retried credit finally lands — either way the destination
        # received the money, so Completed is the truthful terminal state.
        if self.status not in (TransferStatus.POSTED, TransferStatus.NEEDS_RECONCILIATION):
            raise InvalidTransition(f"cannot complete a {self.status} transfer")
        self._record(TransferCompleted())

    def fail(self, reason: FailureReason, detail: str | None = None) -> None:
        if self.status not in _NON_TERMINAL:
            raise InvalidTransition(f"cannot fail a {self.status} transfer")
        self._record(TransferFailed(reason=reason, detail=detail))

    def park_for_reconciliation(self, detail: str) -> None:
        self._assert_status(TransferStatus.POSTED)
        self._record(TransferParkedForReconciliation(detail=detail))

    def reconcile(self, resolution: str, detail: str | None = None) -> None:
        """Resolve a parked transfer (e.g. after refunding the source)."""
        self._assert_status(TransferStatus.NEEDS_RECONCILIATION)
        self._record(TransferReconciled(resolution=resolution, detail=detail))

    def _assert_status(self, expected: TransferStatus) -> None:
        if self.status is not expected:
            raise InvalidTransition(f"expected {expected}, transfer is {self.status}")

    def _apply(self, event: TransferEvent) -> None:
        match event:
            case TransferInitiated(
                source_account_id=source,
                destination_account_id=destination,
                amount=amount,
                reversal_of=reversal_of,
            ):
                self.source_account_id = source
                self.destination_account_id = destination
                self.amount = amount
                self.reversal_of = reversal_of
                self.status = TransferStatus.INITIATED
            case TransferHeld():
                self.status = TransferStatus.HELD
            case TransferPosted(journal_entry_id=journal_entry_id):
                self.journal_entry_id = journal_entry_id
                self.status = TransferStatus.POSTED
            case TransferCompleted():
                self.status = TransferStatus.COMPLETED
            case TransferFailed(reason=reason):
                self.failure_reason = reason
                self.status = TransferStatus.FAILED
            case TransferParkedForReconciliation():
                self.status = TransferStatus.NEEDS_RECONCILIATION
            case TransferReconciled():
                self.status = TransferStatus.RECONCILED
