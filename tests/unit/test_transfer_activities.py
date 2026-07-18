"""Unit tests for the transfer activities, driven directly (no Temporal server).

Activities are plain coroutines, so we can exercise their idempotency guards and
error mapping without a workflow environment.
"""

import pytest
from temporalio.exceptions import ApplicationError

from ledger.domain.accounts.account import Account
from ledger.domain.shared.identifiers import new_account_id, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import FailureReason
from ledger.domain.transfers.transfer import TransferStatus
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.temporal.activities.transfer_activities import TransferActivities
from ledger.temporal.dependencies import LedgerRepositories, build_repositories
from ledger.temporal.messages import FailInput, ParkInput, TransferInput


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


def _repos() -> LedgerRepositories:
    registry = build_event_registry()
    return build_repositories(InMemoryEventStore(registry), registry)


async def _open(repos: LedgerRepositories, *, deposit: int = 0) -> Account:
    account = Account.open(new_account_id(), "USD")
    if deposit:
        account.deposit(usd(deposit))
    assert account.account_id is not None
    await repos.accounts.save(account.account_id, account)
    return account


async def _fixture(*, deposit: int = 1000) -> tuple[TransferActivities, TransferInput]:
    repos = _repos()
    source = await _open(repos, deposit=deposit)
    destination = await _open(repos)
    assert source.account_id is not None and destination.account_id is not None
    acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
    data = TransferInput(
        transfer_id=new_transfer_id(),
        source_account_id=source.account_id,
        destination_account_id=destination.account_id,
        amount=usd(400),
    )
    return acts, data


class TestActivityHappyPath:
    async def test_full_sequence(self) -> None:
        acts, data = await _fixture()
        await acts.record_initiated(data)
        await acts.hold_funds(data)
        entry_id = await acts.post_journal(data)
        assert entry_id
        await acts.settle_debit(data)
        await acts.settle_credit(data)

        transfer = await acts.transfers.load(data.transfer_id)
        assert transfer is not None
        assert transfer.status is TransferStatus.COMPLETED

    async def test_record_initiated_is_idempotent(self) -> None:
        acts, data = await _fixture()
        await acts.record_initiated(data)
        await acts.record_initiated(data)  # no duplicate
        transfer = await acts.transfers.load(data.transfer_id)
        assert transfer is not None
        assert transfer.version == 1

    async def test_record_initiated_self_transfer_is_non_retryable(self) -> None:
        acts, data = await _fixture()
        same = data.model_copy(update={"destination_account_id": data.source_account_id})
        with pytest.raises(ApplicationError) as excinfo:
            await acts.record_initiated(same)
        assert excinfo.value.non_retryable is True
        assert excinfo.value.type == "same_account_transfer"

    async def test_hold_and_post_are_idempotent(self) -> None:
        acts, data = await _fixture()
        await acts.record_initiated(data)
        await acts.hold_funds(data)
        await acts.hold_funds(data)  # retry — no double hold
        first = await acts.post_journal(data)
        second = await acts.post_journal(data)  # retry — same entry
        assert first == second

        source = await acts.accounts.load(data.source_account_id)
        assert source is not None
        assert source.reserved == usd(400)


class TestActivityErrors:
    async def test_hold_unknown_account_raises_terminal(self) -> None:
        repos = _repos()
        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=new_account_id(),  # never opened
            destination_account_id=new_account_id(),
            amount=usd(100),
        )
        with pytest.raises(ApplicationError) as excinfo:
            await acts.hold_funds(data)
        assert excinfo.value.non_retryable
        assert excinfo.value.type == "unknown_account"

    async def test_settle_debit_unknown_account_raises_terminal(self) -> None:
        repos = _repos()
        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=new_account_id(),
            destination_account_id=new_account_id(),
            amount=usd(100),
        )
        with pytest.raises(ApplicationError):
            await acts.settle_debit(data)


class TestCompensationGuards:
    async def test_release_hold_missing_account_is_noop(self) -> None:
        repos = _repos()
        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=new_account_id(),
            destination_account_id=new_account_id(),
            amount=usd(100),
        )
        await acts.release_hold(data)  # no account — silently returns

    async def test_fail_transfer_missing_is_noop(self) -> None:
        acts, data = await _fixture()
        await acts.fail_transfer(
            FailInput(transfer_id=data.transfer_id, reason=FailureReason.OTHER)
        )  # transfer not recorded yet — no-op

    async def test_park_requires_posted(self) -> None:
        acts, data = await _fixture()
        await acts.record_initiated(data)
        await acts.park_transfer(
            ParkInput(transfer_id=data.transfer_id, detail="x")
        )  # still INITIATED — guard skips
        transfer = await acts.transfers.load(data.transfer_id)
        assert transfer is not None
        assert transfer.status is TransferStatus.INITIATED
