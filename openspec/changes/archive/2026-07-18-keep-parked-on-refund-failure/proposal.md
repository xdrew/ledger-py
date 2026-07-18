## Why

In the parked-transfer resolution loop, the retry-credit branch catches
`ActivityError` and stays parked on failure, but the **refund branch does not**.
If `refund_source` fails non-retryably — e.g. the source was frozen or closed
between the debit and the refund, so crediting it raises `AccountNotActive` — the
exception propagates out of the resolution loop and out of `run()`, and the
workflow **fails** instead of remaining a resolvable parked saga. The two branches
should behave symmetrically: a failed resolution leaves the transfer parked for
another decision.

## What Changes

- Wrap the `refund_source` activity call in the resolution loop in
  `try/except ActivityError: continue`, mirroring retry-credit, so a failed refund
  keeps the transfer in `needs_reconciliation` and awaiting a further decision.

## Capabilities

### Modified Capabilities

- `transfers`: a failed resolution attempt (refund or retry) leaves the transfer
  parked rather than failing the workflow.

## Impact

- Code: `src/ledger/temporal/workflows/transfer_workflow.py` (`_await_resolution`).
- Tests: `test_transfer_saga.py` — a refund that fails leaves the saga parked and
  still resolvable (a subsequent working resolution completes it).
