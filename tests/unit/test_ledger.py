"""Unit tests for the double-entry journal and posting service."""

import pytest

from ledger.domain.accounts.account import AccountStatus
from ledger.domain.ledger.journal_entry import JournalEntry
from ledger.domain.ledger.leg import Leg
from ledger.domain.ledger.posting_service import (
    AccountSnapshot,
    AccountStatusReader,
    JournalPostingService,
)
from ledger.domain.shared.errors import (
    AccountNotActive,
    CurrencyMismatch,
    UnbalancedEntry,
    UnknownAccount,
)
from ledger.domain.shared.identifiers import (
    AccountId,
    new_account_id,
    new_journal_entry_id,
)
from ledger.domain.shared.money import Money


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


class FakeReader(AccountStatusReader):
    def __init__(self, snapshots: dict[AccountId, AccountSnapshot]) -> None:
        self._snapshots = snapshots

    async def snapshot(self, account_id: AccountId) -> AccountSnapshot | None:
        return self._snapshots.get(account_id)


class TestJournalEntry:
    def test_balanced_entry_posts(self) -> None:
        src, dst = new_account_id(), new_account_id()
        entry = JournalEntry.post(
            new_journal_entry_id(),
            [Leg.debit(src, usd(100)), Leg.credit(dst, usd(100))],
        )
        assert entry.posted
        assert len(entry.legs) == 2

    def test_unbalanced_entry_rejected(self) -> None:
        src, dst = new_account_id(), new_account_id()
        with pytest.raises(UnbalancedEntry, match="unbalanced"):
            JournalEntry.post(
                new_journal_entry_id(),
                [Leg.debit(src, usd(100)), Leg.credit(dst, usd(90))],
            )

    def test_entry_needs_both_sides(self) -> None:
        src = new_account_id()
        with pytest.raises(UnbalancedEntry, match="at least one debit"):
            JournalEntry.post(new_journal_entry_id(), [Leg.debit(src, usd(100))])

    def test_empty_entry_rejected(self) -> None:
        with pytest.raises(UnbalancedEntry, match="no legs"):
            JournalEntry.post(new_journal_entry_id(), [])


class TestPostingService:
    def _open(self, account_id: AccountId, currency: str = "USD") -> AccountSnapshot:
        return AccountSnapshot(account_id, currency, AccountStatus.OPEN)

    async def test_posts_when_accounts_valid(self) -> None:
        src, dst = new_account_id(), new_account_id()
        reader = FakeReader({src: self._open(src), dst: self._open(dst)})
        service = JournalPostingService(reader)
        entry = await service.post_entry(
            new_journal_entry_id(),
            [Leg.debit(src, usd(100)), Leg.credit(dst, usd(100))],
        )
        assert entry.posted

    async def test_unknown_account_rejected(self) -> None:
        src, dst = new_account_id(), new_account_id()
        reader = FakeReader({src: self._open(src)})  # dst missing
        service = JournalPostingService(reader)
        with pytest.raises(UnknownAccount):
            await service.post_entry(
                new_journal_entry_id(),
                [Leg.debit(src, usd(100)), Leg.credit(dst, usd(100))],
            )

    async def test_frozen_account_rejected(self) -> None:
        src, dst = new_account_id(), new_account_id()
        reader = FakeReader(
            {
                src: AccountSnapshot(src, "USD", AccountStatus.FROZEN),
                dst: self._open(dst),
            }
        )
        service = JournalPostingService(reader)
        with pytest.raises(AccountNotActive):
            await service.post_entry(
                new_journal_entry_id(),
                [Leg.debit(src, usd(100)), Leg.credit(dst, usd(100))],
            )

    async def test_currency_mismatch_rejected(self) -> None:
        src, dst = new_account_id(), new_account_id()
        reader = FakeReader({src: self._open(src, "EUR"), dst: self._open(dst, "USD")})
        service = JournalPostingService(reader)
        with pytest.raises(CurrencyMismatch):
            await service.post_entry(
                new_journal_entry_id(),
                [Leg.debit(src, usd(100)), Leg.credit(dst, usd(100))],
            )
