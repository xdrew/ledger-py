"""End-to-end saga tests on a Temporal time-skipping environment.

Drives the real ``TransferWorkflow`` + activities against an in-memory event
store, asserting the saga's outcomes and the resulting balances. The failing
credit is injected by swapping the ``settle_credit`` activity so the residual
"parked for reconciliation" path is exercised deterministically.
"""

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from temporalio import activity
from temporalio.client import Client, WorkflowHandle
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from ledger.domain.accounts.account import Account
from ledger.domain.shared.identifiers import new_account_id, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.transfer import TransferStatus
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.temporal.activities.transfer_activities import TransferActivities
from ledger.temporal.dependencies import LedgerRepositories, build_repositories
from ledger.temporal.messages import (
    ReconciliationResolution,
    RefundInput,
    TransferInput,
    TransferResult,
)
from ledger.temporal.workflows.transfer_workflow import TransferWorkflow

TASK_QUEUE = "ledger-test"


def usd(amount: int) -> Money:
    return Money(amount=amount, currency="USD")


def _repositories() -> LedgerRepositories:
    registry = build_event_registry()
    store = InMemoryEventStore(registry)
    return build_repositories(store, registry)


async def _open_account(repos: LedgerRepositories, *, deposit: int = 0) -> Account:
    account = Account.open(new_account_id(), "USD")
    if deposit:
        account.deposit(usd(deposit))
    assert account.account_id is not None
    await repos.accounts.save(account.account_id, account)
    return account


def _pydantic_client(env: WorkflowEnvironment) -> Client:
    config = env.client.config()
    config["data_converter"] = pydantic_data_converter
    return Client(**config)


def _saga_activities(
    acts: TransferActivities, *, settle_credit: Callable[..., Any]
) -> list[Callable[..., Any]]:
    """The full activity set with ``settle_credit`` swapped for a test double."""
    return [
        acts.record_initiated,
        acts.hold_funds,
        acts.post_journal,
        acts.settle_debit,
        settle_credit,
        acts.refund_source,
        acts.release_hold,
        acts.fail_transfer,
        acts.park_transfer,
    ]


async def _run(
    env: WorkflowEnvironment,
    repos: LedgerRepositories,
    data: TransferInput,
    activities: list[Callable[..., Any]],
) -> TransferResult:
    client = _pydantic_client(env)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[TransferWorkflow],
        activities=activities,
    ):
        return await client.execute_workflow(
            TransferWorkflow.run,
            data,
            id=f"transfer-{data.transfer_id}",
            task_queue=TASK_QUEUE,
        )


async def _await_status(handle: WorkflowHandle[Any, Any], target: str, tries: int = 500) -> None:
    for _ in range(tries):
        if await handle.query(TransferWorkflow.current_status) == target:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"workflow never reached status {target!r}")


@pytest.fixture
async def env():
    async with await WorkflowEnvironment.start_time_skipping() as environment:
        yield environment


class TestTransferSaga:
    async def test_happy_path_completes(self, env: WorkflowEnvironment) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=1000)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        result = await _run(env, repos, data, acts.all_activities())

        assert result.status is TransferStatus.COMPLETED
        assert result.journal_entry_id is not None

        reloaded_source = await repos.accounts.load(source.account_id)
        reloaded_dest = await repos.accounts.load(destination.account_id)
        assert reloaded_source is not None and reloaded_dest is not None
        assert reloaded_source.available == usd(600)
        assert reloaded_source.reserved == usd(0)
        assert reloaded_dest.available == usd(400)

    async def test_insufficient_funds_fails_with_no_movement(
        self, env: WorkflowEnvironment
    ) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=100)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        result = await _run(env, repos, data, acts.all_activities())

        assert result.status is TransferStatus.FAILED
        assert result.failure_reason is not None
        assert result.failure_reason.value == "insufficient_funds"

        reloaded_source = await repos.accounts.load(source.account_id)
        reloaded_dest = await repos.accounts.load(destination.account_id)
        assert reloaded_source is not None and reloaded_dest is not None
        assert reloaded_source.available == usd(100)  # untouched
        assert reloaded_source.reserved == usd(0)
        assert reloaded_dest.available == usd(0)

    async def test_parked_refund_resolution_makes_source_whole(
        self, env: WorkflowEnvironment
    ) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=1000)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)

        @activity.defn(name="settle_credit")
        async def failing_settle_credit(data: TransferInput) -> None:
            raise ApplicationError(
                "destination unreachable", type="account_not_active", non_retryable=True
            )

        activities = _saga_activities(acts, settle_credit=failing_settle_credit)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        client = _pydantic_client(env)
        async with Worker(
            client, task_queue=TASK_QUEUE, workflows=[TransferWorkflow], activities=activities
        ):
            handle = await client.start_workflow(
                TransferWorkflow.run,
                data,
                id=f"transfer-{data.transfer_id}",
                task_queue=TASK_QUEUE,
            )
            await _await_status(handle, TransferStatus.NEEDS_RECONCILIATION.value)
            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.REFUND_SOURCE
            )
            result = await handle.result()

        assert result.status is TransferStatus.RECONCILED

        reloaded_source = await repos.accounts.load(source.account_id)
        reloaded_dest = await repos.accounts.load(destination.account_id)
        assert reloaded_source is not None and reloaded_dest is not None
        assert reloaded_source.available == usd(1000)  # debited 400, refunded 400 → whole again
        assert reloaded_source.reserved == usd(0)
        assert reloaded_dest.available == usd(0)  # destination never credited

        transfer = await repos.transfers.load(data.transfer_id)
        assert transfer is not None
        assert transfer.status is TransferStatus.RECONCILED

    async def test_parked_retry_credit_resolution_completes(self, env: WorkflowEnvironment) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=1000)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        calls = {"n": 0}

        # Fail the initial credit (exhausting its retries → park), then succeed once
        # the operator retries: the real credit runs and the destination is funded.
        @activity.defn(name="settle_credit")
        async def flaky_settle_credit(data: TransferInput) -> None:
            calls["n"] += 1
            if calls["n"] <= 3:
                raise ApplicationError("temporary glitch", type="conflict")
            await acts.settle_credit(data)

        activities = _saga_activities(acts, settle_credit=flaky_settle_credit)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        client = _pydantic_client(env)
        async with Worker(
            client, task_queue=TASK_QUEUE, workflows=[TransferWorkflow], activities=activities
        ):
            handle = await client.start_workflow(
                TransferWorkflow.run,
                data,
                id=f"transfer-{data.transfer_id}",
                task_queue=TASK_QUEUE,
            )
            await _await_status(handle, TransferStatus.NEEDS_RECONCILIATION.value)
            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.RETRY_CREDIT
            )
            result = await handle.result()

        assert result.status is TransferStatus.COMPLETED
        reloaded_source = await repos.accounts.load(source.account_id)
        reloaded_dest = await repos.accounts.load(destination.account_id)
        assert reloaded_source is not None and reloaded_dest is not None
        assert reloaded_source.available == usd(600)  # money left the source
        assert reloaded_dest.available == usd(400)  # credited exactly once on retry

    async def test_parked_retry_that_still_fails_stays_parked_then_refunds(
        self, env: WorkflowEnvironment
    ) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=1000)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        calls = {"n": 0}

        @activity.defn(name="settle_credit")
        async def always_failing_credit(data: TransferInput) -> None:
            calls["n"] += 1
            raise ApplicationError("temporary glitch", type="conflict")

        activities = _saga_activities(acts, settle_credit=always_failing_credit)
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        client = _pydantic_client(env)
        async with Worker(
            client, task_queue=TASK_QUEUE, workflows=[TransferWorkflow], activities=activities
        ):
            handle = await client.start_workflow(
                TransferWorkflow.run,
                data,
                id=f"transfer-{data.transfer_id}",
                task_queue=TASK_QUEUE,
            )
            await _await_status(handle, TransferStatus.NEEDS_RECONCILIATION.value)
            attempts_after_park = calls["n"]

            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.RETRY_CREDIT
            )
            # Wait until the retry has exhausted its attempts (still failing).
            for _ in range(500):
                if calls["n"] >= attempts_after_park + 3:
                    break
                await asyncio.sleep(0.02)
            assert calls["n"] >= attempts_after_park + 3
            assert await handle.query(TransferWorkflow.current_status) == (
                TransferStatus.NEEDS_RECONCILIATION.value
            )

            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.REFUND_SOURCE
            )
            result = await handle.result()

        assert result.status is TransferStatus.RECONCILED
        reloaded_source = await repos.accounts.load(source.account_id)
        assert reloaded_source is not None
        assert reloaded_source.available == usd(1000)  # refunded after retry failed

    async def test_failed_refund_keeps_parked_then_resolves(self, env: WorkflowEnvironment) -> None:
        repos = _repositories()
        source = await _open_account(repos, deposit=1000)
        destination = await _open_account(repos)
        assert source.account_id is not None
        assert destination.account_id is not None

        acts = TransferActivities(repos.accounts, repos.journals, repos.transfers)
        refund_calls = {"n": 0}

        @activity.defn(name="settle_credit")
        async def failing_settle_credit(data: TransferInput) -> None:
            raise ApplicationError(
                "destination unreachable", type="account_not_active", non_retryable=True
            )

        # First refund fails (non-retryable); the second delegates to the real refund.
        @activity.defn(name="refund_source")
        async def flaky_refund(data: RefundInput) -> None:
            refund_calls["n"] += 1
            if refund_calls["n"] == 1:
                raise ApplicationError(
                    "source frozen", type="account_not_active", non_retryable=True
                )
            await acts.refund_source(data)

        activities: list[Callable[..., Any]] = [
            acts.record_initiated,
            acts.hold_funds,
            acts.post_journal,
            acts.settle_debit,
            failing_settle_credit,
            flaky_refund,
            acts.release_hold,
            acts.fail_transfer,
            acts.park_transfer,
        ]
        data = TransferInput(
            transfer_id=new_transfer_id(),
            source_account_id=source.account_id,
            destination_account_id=destination.account_id,
            amount=usd(400),
        )
        client = _pydantic_client(env)
        async with Worker(
            client, task_queue=TASK_QUEUE, workflows=[TransferWorkflow], activities=activities
        ):
            handle = await client.start_workflow(
                TransferWorkflow.run,
                data,
                id=f"transfer-{data.transfer_id}",
                task_queue=TASK_QUEUE,
            )
            await _await_status(handle, TransferStatus.NEEDS_RECONCILIATION.value)

            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.REFUND_SOURCE
            )
            for _ in range(500):  # wait until the failing refund was attempted
                if refund_calls["n"] >= 1:
                    break
                await asyncio.sleep(0.02)
            assert refund_calls["n"] >= 1
            # The workflow survived the failed refund and is still parked.
            assert await handle.query(TransferWorkflow.current_status) == (
                TransferStatus.NEEDS_RECONCILIATION.value
            )

            await handle.signal(
                TransferWorkflow.resolve_reconciliation, ReconciliationResolution.REFUND_SOURCE
            )
            result = await handle.result()

        assert result.status is TransferStatus.RECONCILED
        reloaded_source = await repos.accounts.load(source.account_id)
        assert reloaded_source is not None
        assert reloaded_source.available == usd(1000)  # made whole on the second refund
