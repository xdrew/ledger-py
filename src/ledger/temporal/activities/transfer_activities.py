"""Temporal activities — the only place the saga touches persistent state.

Every activity is idempotent: account moves dedupe on their deterministic
``operation_id``, journal posting checks for an existing entry, and milestone
recording is guarded by the transfer's current status. Terminal domain errors
become non-retryable ``ApplicationError``s (the workflow maps them to a
``FailureReason``); transient errors such as ``ConcurrencyConflict`` propagate as
retryable so Temporal reloads and tries again.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from temporalio import activity
from temporalio.exceptions import ApplicationError

from ledger.domain.accounts.account import Account
from ledger.domain.ledger.journal_entry import JournalEntry
from ledger.domain.ledger.leg import Leg
from ledger.domain.ledger.posting_service import (
    AccountSnapshot,
    JournalPostingService,
)
from ledger.domain.shared.errors import (
    AccountNotActive,
    CurrencyMismatch,
    DomainError,
    InsufficientFunds,
    InvalidAmount,
    SameAccountTransfer,
    UnbalancedEntry,
    UnknownAccount,
)
from ledger.domain.shared.identifiers import AccountId, TransferId
from ledger.domain.transfers.operations import journal_entry_id_for, operation_id
from ledger.domain.transfers.transfer import Transfer, TransferStatus
from ledger.eventstore.records import EventMetadata
from ledger.eventstore.repository import EventSourcedRepository
from ledger.temporal.messages import FailInput, ParkInput, RefundInput, TransferInput

_NON_TERMINAL = frozenset({TransferStatus.INITIATED, TransferStatus.HELD, TransferStatus.POSTED})


def _terminal(err: DomainError) -> ApplicationError:
    """A domain rule was violated — do not retry; hand the code to the workflow."""
    return ApplicationError(err.message, type=err.code, non_retryable=True)


def _meta(transfer_id: TransferId, traceparent: str | None = None) -> EventMetadata:
    """Envelope tying a transfer's cross-stream events together and carrying trace."""
    return EventMetadata(correlation_id=transfer_id, traceparent=traceparent)


class _RepositoryStatusReader:
    """Reads live account status straight from the aggregate (no projection lag)."""

    def __init__(self, accounts: EventSourcedRepository[Account]) -> None:
        self._accounts = accounts

    async def snapshot(self, account_id: AccountId) -> AccountSnapshot | None:
        account = await self._accounts.load(account_id)
        if account is None:
            return None
        return AccountSnapshot(account_id, account.currency, account.status)


@dataclass(slots=True)
class TransferActivities:
    accounts: EventSourcedRepository[Account]
    journals: EventSourcedRepository[JournalEntry]
    transfers: EventSourcedRepository[Transfer]

    @activity.defn
    async def record_initiated(self, data: TransferInput) -> None:
        if await self.transfers.load(data.transfer_id) is not None:
            return
        try:
            transfer = Transfer.initiate(
                data.transfer_id,
                data.source_account_id,
                data.destination_account_id,
                data.amount,
                data.reversal_of,
            )
        except (SameAccountTransfer, InvalidAmount) as err:
            # Bad input, not a transient fault — fail fast instead of retrying.
            raise _terminal(err) from err
        await self.transfers.save(
            data.transfer_id, transfer, _meta(data.transfer_id, data.traceparent)
        )

    @activity.defn
    async def hold_funds(self, data: TransferInput) -> None:
        op = operation_id(data.transfer_id, "hold")
        try:
            source = await self.accounts.load(data.source_account_id)
            if source is None:
                raise UnknownAccount(str(data.source_account_id))
            source.hold(data.amount, op)
            await self.accounts.save(
                data.source_account_id, source, _meta(data.transfer_id, data.traceparent)
            )
        except (
            InsufficientFunds,
            AccountNotActive,
            CurrencyMismatch,
            UnknownAccount,
        ) as err:
            raise _terminal(err) from err

        transfer = await self.transfers.load(data.transfer_id)
        if transfer is not None and transfer.status is TransferStatus.INITIATED:
            transfer.mark_held()
            await self.transfers.save(
                data.transfer_id, transfer, _meta(data.transfer_id, data.traceparent)
            )

    @activity.defn
    async def post_journal(self, data: TransferInput) -> str:
        entry_id = journal_entry_id_for(data.transfer_id)
        if await self.journals.load(entry_id) is None:
            service = JournalPostingService(_RepositoryStatusReader(self.accounts))
            legs = [
                Leg.debit(data.source_account_id, data.amount),
                Leg.credit(data.destination_account_id, data.amount),
            ]
            try:
                entry = await service.post_entry(entry_id, legs, reference=str(data.transfer_id))
            except (
                UnknownAccount,
                AccountNotActive,
                CurrencyMismatch,
                UnbalancedEntry,
            ) as err:
                raise _terminal(err) from err
            await self.journals.save(entry_id, entry, _meta(data.transfer_id, data.traceparent))

        transfer = await self.transfers.load(data.transfer_id)
        if transfer is not None and transfer.status is TransferStatus.HELD:
            transfer.mark_posted(entry_id)
            await self.transfers.save(
                data.transfer_id, transfer, _meta(data.transfer_id, data.traceparent)
            )
        return str(entry_id)

    @activity.defn
    async def settle_debit(self, data: TransferInput) -> None:
        op = operation_id(data.transfer_id, "debit")
        try:
            source = await self.accounts.load(data.source_account_id)
            if source is None:
                raise UnknownAccount(str(data.source_account_id))
            source.debit(data.amount, op)
            await self.accounts.save(
                data.source_account_id, source, _meta(data.transfer_id, data.traceparent)
            )
        except (InsufficientFunds, AccountNotActive, UnknownAccount) as err:
            raise _terminal(err) from err

    @activity.defn
    async def settle_credit(self, data: TransferInput) -> None:
        op = operation_id(data.transfer_id, "credit")
        try:
            destination = await self.accounts.load(data.destination_account_id)
            if destination is None:
                raise UnknownAccount(str(data.destination_account_id))
            destination.credit(data.amount, op)
            await self.accounts.save(
                data.destination_account_id, destination, _meta(data.transfer_id, data.traceparent)
            )
        except (AccountNotActive, UnknownAccount) as err:
            raise _terminal(err) from err

        transfer = await self.transfers.load(data.transfer_id)
        # Completable from Posted (happy path) or NeedsReconciliation (a retried
        # credit resolving a parked transfer). Either way the money reached the
        # destination, so Completed is truthful.
        if transfer is not None and transfer.status in (
            TransferStatus.POSTED,
            TransferStatus.NEEDS_RECONCILIATION,
        ):
            transfer.complete()
            await self.transfers.save(
                data.transfer_id, transfer, _meta(data.transfer_id, data.traceparent)
            )

    @activity.defn
    async def refund_source(self, data: RefundInput) -> None:
        """Resolve a parked transfer by returning the debited funds to the source.

        The debit drew from the source's reserved bucket, so the money settled out
        entirely; the refund credits it back as spendable ``available`` funds under
        a distinct deterministic op id, then records the reconciliation. Idempotent
        under retry and status-guarded so it applies at most once.
        """
        op = operation_id(data.transfer_id, "refund")
        try:
            source = await self.accounts.load(data.source_account_id)
            if source is None:
                raise UnknownAccount(str(data.source_account_id))
            source.credit(data.amount, op)
            await self.accounts.save(data.source_account_id, source, _meta(data.transfer_id))
        except (AccountNotActive, UnknownAccount) as err:
            raise _terminal(err) from err

        transfer = await self.transfers.load(data.transfer_id)
        if transfer is not None and transfer.status is TransferStatus.NEEDS_RECONCILIATION:
            transfer.reconcile("refunded", "funds returned to source")
            await self.transfers.save(data.transfer_id, transfer, _meta(data.transfer_id))

    @activity.defn
    async def release_hold(self, data: TransferInput) -> None:
        """Compensation: return held funds to the source's available balance."""
        op = operation_id(data.transfer_id, "release")
        source = await self.accounts.load(data.source_account_id)
        if source is None:
            return
        source.release_hold(data.amount, op)
        await self.accounts.save(
            data.source_account_id, source, _meta(data.transfer_id, data.traceparent)
        )

    @activity.defn
    async def fail_transfer(self, data: FailInput) -> None:
        transfer = await self.transfers.load(data.transfer_id)
        if transfer is None or transfer.status not in _NON_TERMINAL:
            return
        transfer.fail(data.reason, data.detail)
        await self.transfers.save(data.transfer_id, transfer, _meta(data.transfer_id))

    @activity.defn
    async def park_transfer(self, data: ParkInput) -> None:
        transfer = await self.transfers.load(data.transfer_id)
        if transfer is None or transfer.status is not TransferStatus.POSTED:
            return
        transfer.park_for_reconciliation(data.detail)
        await self.transfers.save(data.transfer_id, transfer, _meta(data.transfer_id))

    def all_activities(self) -> list[Callable[..., Any]]:
        """The bound activity callables to register with the worker."""
        return [
            self.record_initiated,
            self.hold_funds,
            self.post_journal,
            self.settle_debit,
            self.settle_credit,
            self.refund_source,
            self.release_hold,
            self.fail_transfer,
            self.park_transfer,
        ]
