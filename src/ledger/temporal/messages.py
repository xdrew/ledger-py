"""Serializable messages crossing the workflow/activity boundary.

Pydantic models throughout, carried by Temporal's pydantic data converter.
"""

from enum import StrEnum

from pydantic import BaseModel

from ledger.domain.shared.identifiers import AccountId, JournalEntryId, TransferId
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import FailureReason
from ledger.domain.transfers.transfer import TransferStatus


class ReconciliationResolution(StrEnum):
    """An operator's decision for a parked (needs-reconciliation) transfer."""

    RETRY_CREDIT = "retry_credit"  # re-attempt the destination credit
    REFUND_SOURCE = "refund_source"  # return the debited funds to the source


class TransferInput(BaseModel):
    transfer_id: TransferId
    source_account_id: AccountId
    destination_account_id: AccountId
    amount: Money
    reversal_of: TransferId | None = None
    # W3C trace context carried from the initiating request through the saga.
    traceparent: str | None = None


class FailInput(BaseModel):
    transfer_id: TransferId
    reason: FailureReason
    detail: str | None = None


class ParkInput(BaseModel):
    transfer_id: TransferId
    detail: str


class RefundInput(BaseModel):
    transfer_id: TransferId
    source_account_id: AccountId
    amount: Money


class TransferResult(BaseModel):
    transfer_id: TransferId
    status: TransferStatus
    journal_entry_id: JournalEntryId | None = None
    failure_reason: FailureReason | None = None
    detail: str | None = None
