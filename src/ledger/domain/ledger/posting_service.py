"""Posting service — validates accounts before building a balanced journal entry.

Reads account status/currency through the :class:`AccountStatusReader` port so
the domain stays independent of how that state is stored (a projection today).
It returns the aggregate; persisting it is the caller's (activity's) job.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from ledger.domain.accounts.account import AccountStatus
from ledger.domain.ledger.journal_entry import JournalEntry
from ledger.domain.ledger.leg import Leg
from ledger.domain.shared.errors import (
    AccountNotActive,
    CurrencyMismatch,
    UnknownAccount,
)
from ledger.domain.shared.identifiers import AccountId, JournalEntryId


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    account_id: AccountId
    currency: str
    status: AccountStatus


class AccountStatusReader(Protocol):
    async def snapshot(self, account_id: AccountId) -> AccountSnapshot | None: ...


class JournalPostingService:
    def __init__(self, reader: AccountStatusReader) -> None:
        self._reader = reader

    async def post_entry(
        self,
        entry_id: JournalEntryId,
        legs: Sequence[Leg],
        reference: str | None = None,
    ) -> JournalEntry:
        snapshots = await self._resolve_accounts(legs)
        for leg in legs:
            snapshot = snapshots[leg.account_id]
            if snapshot.currency != leg.amount.currency:
                raise CurrencyMismatch(
                    f"account {leg.account_id} is {snapshot.currency}, leg is {leg.amount.currency}"
                )
        return JournalEntry.post(entry_id, legs, reference)

    async def _resolve_accounts(self, legs: Sequence[Leg]) -> dict[AccountId, AccountSnapshot]:
        resolved: dict[AccountId, AccountSnapshot] = {}
        for account_id in {leg.account_id for leg in legs}:
            snapshot = await self._reader.snapshot(account_id)
            if snapshot is None:
                raise UnknownAccount(str(account_id))
            if snapshot.status is not AccountStatus.OPEN:
                raise AccountNotActive(f"account {account_id} is {snapshot.status}")
            resolved[account_id] = snapshot
        return resolved
