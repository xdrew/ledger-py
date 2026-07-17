"""The transfer saga as a Temporal workflow.

Deterministic orchestration only — all state access happens in activities. The
workflow keeps a compensation stack (just the hold, here) and unwinds it on any
failure *before* the source debit. After the debit the money has moved, so a
failing destination credit cannot be compensated: the workflow parks the
transfer in ``needs_reconciliation`` (loudly visible in the Temporal UI) instead
of recording a false failure. See ADR-0003.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from uuid import UUID

    from ledger.domain.transfers.events import FailureReason
    from ledger.domain.transfers.transfer import TransferStatus
    from ledger.temporal.activities.transfer_activities import TransferActivities
    from ledger.temporal.messages import (
        FailInput,
        ParkInput,
        ReconciliationResolution,
        RefundInput,
        TransferInput,
        TransferResult,
    )

_ACTIVITY_TIMEOUT = timedelta(seconds=30)
# Retries absorb transient conflicts (optimistic concurrency); non-retryable
# ApplicationErrors (domain-rule violations) stop immediately regardless.
_DEFAULT_RETRY = RetryPolicy(maximum_attempts=5)
_CREDIT_RETRY = RetryPolicy(maximum_attempts=3)


def _reason_from(err: ActivityError) -> tuple[FailureReason, str]:
    cause = err.cause
    if isinstance(cause, ApplicationError):
        detail = cause.message
        app_type = cause.type
        if app_type in (None, "conflict", "ConcurrencyConflict"):
            return FailureReason.CONFLICT, detail
        try:
            return FailureReason(app_type), detail
        except ValueError:
            return FailureReason.OTHER, detail
    return FailureReason.OTHER, str(cause) if cause is not None else str(err)


@workflow.defn
class TransferWorkflow:
    def __init__(self) -> None:
        self._status: TransferStatus = TransferStatus.INITIATED
        self._failure: FailureReason | None = None
        self._resolution: ReconciliationResolution | None = None

    @workflow.query
    def current_status(self) -> str:
        return self._status.value

    @workflow.query
    def failure_reason(self) -> str | None:
        return self._failure.value if self._failure is not None else None

    @workflow.signal
    def resolve_reconciliation(self, decision: ReconciliationResolution) -> None:
        """Operator decision for a parked transfer; consumed by the park loop."""
        self._resolution = decision

    @workflow.run
    async def run(self, data: TransferInput) -> TransferResult:
        await workflow.execute_activity_method(
            TransferActivities.record_initiated,
            data,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_DEFAULT_RETRY,
        )

        holding = False
        try:
            await workflow.execute_activity_method(
                TransferActivities.hold_funds,
                data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )
            self._status = TransferStatus.HELD
            holding = True

            entry_id = await workflow.execute_activity_method(
                TransferActivities.post_journal,
                data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )
            self._status = TransferStatus.POSTED

            await workflow.execute_activity_method(
                TransferActivities.settle_debit,
                data,
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )
            # Money has left the source; the hold is consumed. No going back.
            holding = False

            try:
                await workflow.execute_activity_method(
                    TransferActivities.settle_credit,
                    data,
                    start_to_close_timeout=_ACTIVITY_TIMEOUT,
                    retry_policy=_CREDIT_RETRY,
                )
            except ActivityError as credit_err:
                _, detail = _reason_from(credit_err)
                await workflow.execute_activity_method(
                    TransferActivities.park_transfer,
                    ParkInput(
                        transfer_id=data.transfer_id,
                        detail=f"credit failed after debit: {detail}",
                    ),
                    start_to_close_timeout=_ACTIVITY_TIMEOUT,
                    retry_policy=_DEFAULT_RETRY,
                )
                return await self._await_resolution(data, entry_id)

            self._status = TransferStatus.COMPLETED
            return TransferResult(
                transfer_id=data.transfer_id,
                status=self._status,
                journal_entry_id=UUID(entry_id),
            )

        except ActivityError as err:
            reason, detail = _reason_from(err)
            if holding:
                await workflow.execute_activity_method(
                    TransferActivities.release_hold,
                    data,
                    start_to_close_timeout=_ACTIVITY_TIMEOUT,
                    retry_policy=_DEFAULT_RETRY,
                )
            await workflow.execute_activity_method(
                TransferActivities.fail_transfer,
                FailInput(transfer_id=data.transfer_id, reason=reason, detail=detail),
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )
            self._status = TransferStatus.FAILED
            self._failure = reason
            return TransferResult(
                transfer_id=data.transfer_id,
                status=self._status,
                failure_reason=reason,
                detail=detail,
            )

    async def _await_resolution(self, data: TransferInput, entry_id: str) -> TransferResult:
        """Park in ``needs_reconciliation`` and wait for operator resolution.

        The saga stays alive (visible in the Temporal UI, status queryable) until an
        operator signals a decision: retry the credit (completes if it now lands, else
        stays parked) or refund the source (terminal ``Reconciled``).
        """
        self._status = TransferStatus.NEEDS_RECONCILIATION
        while True:
            await workflow.wait_condition(lambda: self._resolution is not None)
            decision, self._resolution = self._resolution, None

            if decision is ReconciliationResolution.RETRY_CREDIT:
                try:
                    await workflow.execute_activity_method(
                        TransferActivities.settle_credit,
                        data,
                        start_to_close_timeout=_ACTIVITY_TIMEOUT,
                        retry_policy=_CREDIT_RETRY,
                    )
                except ActivityError:
                    continue  # still cannot credit; remain parked for a further decision
                self._status = TransferStatus.COMPLETED
                return TransferResult(
                    transfer_id=data.transfer_id,
                    status=self._status,
                    journal_entry_id=UUID(entry_id),
                )

            await workflow.execute_activity_method(
                TransferActivities.refund_source,
                RefundInput(
                    transfer_id=data.transfer_id,
                    source_account_id=data.source_account_id,
                    amount=data.amount,
                ),
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_DEFAULT_RETRY,
            )
            self._status = TransferStatus.RECONCILED
            return TransferResult(
                transfer_id=data.transfer_id,
                status=self._status,
                journal_entry_id=UUID(entry_id),
                detail="refunded to source",
            )
