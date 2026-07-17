## 1. Domain

- [x] 1.1 Add `TransferStatus.RECONCILED` and `TransferReconciled(resolution, detail)`
  event; extend `TransferEvent` union and `TRANSFER_EVENT_TYPES`.
- [x] 1.2 Add `Transfer.reconcile(resolution, detail)` allowed only from
  `NeedsReconciliation`; broaden `Transfer.complete()` to allow `Posted` or
  `NeedsReconciliation`; apply both in `_apply`.
- [x] 1.3 Domain tests in `tests/unit/test_transfer.py` for the new transitions
  and their rejections.

## 2. Messages & activities

- [x] 2.1 Add `ReconciliationResolution` StrEnum (`retry_credit`, `refund_source`)
  and a `RefundInput` message in `temporal/messages.py`.
- [x] 2.2 Add `refund_source` activity: credit the source's available balance
  with `operation_id(transfer_id, "refund")`, then `reconcile("refunded")`;
  idempotent and status-guarded.
- [x] 2.3 Broaden `settle_credit`'s completion guard to complete from `Posted`
  **or** `NeedsReconciliation`; register `refund_source` in `all_activities()`.

## 3. Workflow

- [x] 3.1 Add a `resolve_reconciliation` signal setting the pending resolution.
- [x] 3.2 After parking, replace the immediate return with an await-resolution
  loop: retry-credit → `Completed` on success (else stay parked); refund-source →
  `Reconciled`.

## 4. Saga tests (time-skipping env)

- [x] 4.1 Update the existing park case to start the workflow, wait for the
  `needs_reconciliation` status via query, signal `refund_source`, and assert
  `Reconciled` with the source restored and destination untouched.
- [x] 4.2 Add a retry-credit-success case (destination creditable) → `Completed`,
  destination credited exactly once.
- [x] 4.3 Add a retry-then-refund case (retry still fails, then refund) →
  `Reconciled`.

## 5. Docs & quality gate

- [x] 5.1 Extend `docs/adr/0003-*.md` consequences: resolution mechanism implemented.
- [x] 5.2 `ruff check` + `ruff format --check` + `pyright` (strict) clean.
- [x] 5.3 `uv run pytest` green.
- [x] 5.4 `openspec validate add-transfer-reconciliation --strict` passes.
