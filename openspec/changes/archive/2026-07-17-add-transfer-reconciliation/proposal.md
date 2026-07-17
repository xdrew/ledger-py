## Why

ADR-0003 says a residual credit failure parks the transfer in
`needs_reconciliation` "awaiting an operator or a reconciliation activity" — but
no resolution path exists. Today the workflow records the parked state and
*returns*, so a parked transfer is a terminal dead end: money has left the source,
never reached the destination, and nothing can drive it to resolution. The
`reversal_of` field is threaded through the model but never used. The headline
guarantee ("stuck sagas are a first-class, resolvable state") is therefore only
half-built.

## What Changes

- The transfer workflow, after parking, **stays alive and awaits an operator
  resolution** via a Temporal signal instead of returning — the honest
  realization of "durable execution keeps the stuck saga visible *and*
  actionable".
- Two resolutions:
  - **refund-source**: credit the debited amount back to the source's available
    balance (idempotent `operation_id`), record a terminal `Reconciled` state.
    Used when the destination genuinely cannot be credited (closed/frozen/gone).
  - **retry-credit**: re-attempt the destination credit; on success the transfer
    truthfully reaches `Completed`; on continued failure it remains parked and
    awaits the next decision.
- Domain: add `TransferStatus.RECONCILED` and a `TransferReconciled` milestone
  event; add the `NeedsReconciliation → Reconciled` and
  `NeedsReconciliation → Completed` transitions; enforce them.
- Saga: add a `refund_source` activity and a resolution signal; the audit stream
  records the resolution.
- **BREAKING** (test-facing, not yet in production): the park path no longer
  returns immediately — callers observe the parked state via workflow query and
  drive resolution via signal. The existing park integration test is updated to
  match; new tests cover both resolutions.

Out of scope (deliberately, to keep one capability per change): an HTTP endpoint
to trigger resolution — operators resolve via the Temporal signal (UI/CLI) here;
an `api` change can expose it later.

## Capabilities

### Modified Capabilities

- `transfers`: the "residual credit failure parks for reconciliation" requirement
  is strengthened — the saga now awaits and applies an operator resolution rather
  than terminating at the parked state; a new requirement defines the two
  resolution outcomes and the transitions they drive.

## Impact

- Code: `src/ledger/domain/transfers/transfer.py` (status, transition,
  `_apply`), `transfers/events.py` (new event + union + registry tuple),
  `temporal/workflows/transfer_workflow.py` (signal + await-resolution loop),
  `temporal/activities/transfer_activities.py` (`refund_source`; broaden the
  credit-completion guard to allow completing from `NeedsReconciliation`),
  `temporal/messages.py` (resolution enum / input).
- Tests: update `test_transfer_saga.py` park case to drive a signal; add
  refund-resolution and retry-credit-resolution cases; add domain transition
  tests in `test_transfer.py`.
- Docs: extend ADR-0003 consequences to note the resolution mechanism is now
  implemented.
