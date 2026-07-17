## Context

When the destination credit fails *after* the source debit has applied, the hold
is consumed and money has left the source. ADR-0003 rules out recording a false
`Failed`; the saga parks in `needs_reconciliation`. The gap: parking is terminal
in code. There is no way to make the source whole again or to complete the
transfer once the destination becomes creditable. This change builds the
resolution path Temporal makes natural — a long-lived workflow waiting on a
signal.

## Goals / Non-Goals

**Goals**
- A parked transfer is resolvable to a truthful terminal state.
- The saga stays durably alive and queryable while parked (not a returned
  dead end).
- Both movements are idempotent and auditable.

**Non-Goals**
- Automatic resolution policy (auto-refund after N hours). The decision is an
  operator's; a scheduled driver can be layered on later.
- HTTP triggering (belongs to the `api` capability).
- Automatic double-entry reversal journal entry. The refund is modeled as a
  balance credit back to the source with a `TransferReconciled` audit event;
  a compensating journal entry can be a later refinement.

## Decisions

### 1. The workflow awaits a resolution signal after parking

After recording `TransferParkedForReconciliation`, the workflow loops:

```python
self._status = NEEDS_RECONCILIATION
while True:
    await workflow.wait_condition(lambda: self._resolution is not None)
    decision, self._resolution = self._resolution, None
    if decision is ReconciliationResolution.RETRY_CREDIT:
        try:
            await execute settle_credit(data)          # idempotent, op="credit"
            self._status = COMPLETED
            return TransferResult(status=COMPLETED, journal_entry_id=...)
        except ActivityError:
            continue                                    # still stuck; await again
    else:  # REFUND_SOURCE
        await execute refund_source(RefundInput(...))
        self._status = RECONCILED
        return TransferResult(status=RECONCILED, detail="refunded to source")
```

A `@workflow.signal` handler sets `self._resolution`. The existing status query
already surfaces `needs_reconciliation` while parked. This is idiomatic durable
execution: the stuck saga is visible in the Temporal UI and an operator drives it
by signalling.

Rationale for awaiting rather than returning-then-restarting: it keeps a single
workflow as the whole lifecycle of one transfer (one id, one history), which is
exactly the audit story the project sells. The only cost is a long-lived
workflow, which Temporal is built for.

### 2. Refund credits the source's available balance

`settle_debit` drew the amount from the source's `reserved` bucket, so the money
is already gone from the source entirely. The refund returns it as an inflow to
`available` via `Account.credit(amount, operation_id(transfer_id, "refund"))` —
a distinct, deterministic op id, so retries of the refund activity are safe
no-ops. After crediting, the activity records `Transfer.reconcile("refunded")`.

Why credit `available` and not re-`reserve`: from the account's perspective the
funds settled out and are now being returned; there is no outstanding hold to
restore. This matches how a real refund lands — as spendable money.

### 3. Retry-credit completes truthfully

`settle_credit` is already idempotent on `op="credit"` and was never applied on
the failed attempt, so re-running it credits the destination exactly once. Its
completion guard is broadened to fire `Transfer.complete()` when the transfer is
in `Posted` **or** `NeedsReconciliation`, so a resolved retry records the truthful
`TransferCompleted`.

### 4. Domain state machine additions

- New status `RECONCILED` (terminal).
- New event `TransferReconciled(resolution: str, detail: str | None)`.
- New command `Transfer.reconcile(resolution, detail)` — allowed only from
  `NeedsReconciliation`.
- `Transfer.complete()` allowed from `Posted` or `NeedsReconciliation`.
- Transitions enforced; invalid ones raise `InvalidTransition`.

`RECONCILED` is distinct from `COMPLETED`: completed means the destination
received the money; reconciled means the transfer was unwound back to the source.
Keeping them separate preserves an honest audit trail.

## Serialization / registry

`TransferReconciled` is added to `TransferEvent`, `TRANSFER_EVENT_TYPES` (so
`build_event_registry` picks it up), and the workflow/messages boundary gains a
`ReconciliationResolution` StrEnum and a `RefundInput` model, carried by the
pydantic data converter like the other messages.

## Testing strategy

- **Domain** (`test_transfer.py`): `reconcile` only from `NeedsReconciliation`;
  `complete` allowed from `Posted` and `NeedsReconciliation`; illegal transitions
  rejected; `_apply` sets `RECONCILED`.
- **Saga** (`test_transfer_saga.py`, time-skipping env):
  - Update the park case: start the workflow (handle), wait until the status
    query reports `needs_reconciliation`, then signal `REFUND_SOURCE`; assert the
    result is `RECONCILED` and the source's available balance is fully restored,
    destination untouched.
  - New: park then signal `RETRY_CREDIT` against a now-creditable destination;
    assert `Completed` and the destination is credited exactly once.
  - New: park, signal `RETRY_CREDIT` while still failing (stays parked), then
    signal `REFUND_SOURCE`; assert `RECONCILED`.

## Risks / Tradeoffs

- Long-lived parked workflows accumulate until resolved — intended; they are the
  actionable backlog. A future scheduled driver / timeout policy can bound them.
- Broadening `complete()`'s allowed predecessors slightly widens the state
  machine; covered by explicit transition tests.
