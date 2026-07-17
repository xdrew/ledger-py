"""Request/response models for the HTTP API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from ledger.domain.accounts.account import AccountStatus
from ledger.domain.shared.identifiers import AccountId, JournalEntryId, TransferId
from ledger.domain.shared.money import CurrencyCode
from ledger.domain.transfers.events import FailureReason
from ledger.domain.transfers.transfer import TransferStatus
from ledger.temporal.messages import ReconciliationResolution


class OpenAccountRequest(BaseModel):
    currency: CurrencyCode


class DepositRequest(BaseModel):
    amount: int = Field(gt=0, description="amount in minor units")
    currency: CurrencyCode


class AccountResponse(BaseModel):
    account_id: AccountId
    currency: str
    status: AccountStatus
    available: int
    reserved: int
    total: int


class StatementLineResponse(BaseModel):
    global_position: int
    kind: str
    amount: int
    currency: str
    occurred_at: datetime


class EventResponse(BaseModel):
    global_position: int
    version: int
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]


class CreateTransferRequest(BaseModel):
    source_account_id: AccountId
    destination_account_id: AccountId
    amount: int = Field(gt=0, description="amount in minor units")
    currency: CurrencyCode


class TransferAccepted(BaseModel):
    transfer_id: TransferId
    status: str


class ResolveTransferRequest(BaseModel):
    resolution: ReconciliationResolution


class TransferResponse(BaseModel):
    transfer_id: TransferId
    status: TransferStatus
    source_account_id: AccountId | None
    destination_account_id: AccountId | None
    amount: int | None
    currency: str | None
    journal_entry_id: JournalEntryId | None
    failure_reason: FailureReason | None
