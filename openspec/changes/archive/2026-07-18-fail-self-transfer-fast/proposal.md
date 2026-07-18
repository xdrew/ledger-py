## Why

The self-transfer guard lives only in `Transfer.initiate`, which runs inside the
`record_initiated` activity — not on the API path. So `POST /api/transfers` with
equal source and destination returns `202 Accepted`, starts a workflow, and the
activity raises `SameAccountTransfer` as a *retryable* error (it is not wrapped as
non-retryable), so Temporal retries it five times and then fails the workflow. The
client got a `202` for a transfer that silently dies, and the `422` mapping added
for `same_account_transfer` is never reached on this path. The guard should reject
fast, at the edge.

## What Changes

- `POST /api/transfers` validates that source and destination differ **before**
  claiming idempotency or starting the saga, raising `SameAccountTransfer` →
  `422` via the existing problem-details handler.
- Defense-in-depth: `record_initiated` converts a `SameAccountTransfer` (and other
  domain errors from `initiate`) into a **non-retryable** `ApplicationError`, so a
  bad input that somehow reaches the activity fails immediately instead of
  retrying five times.

## Capabilities

### Modified Capabilities

- `transfers`: a self-transfer is rejected at the API before the saga starts, and
  fails fast (non-retryable) if it reaches the activity.

## Impact

- Code: `src/ledger/api/routers/transfers.py` (edge validation),
  `src/ledger/temporal/activities/transfer_activities.py` (`record_initiated`
  wraps domain errors as terminal).
- Tests: `test_api.py` — self-transfer POST → `422`, gateway not started;
  `test_transfer_activities.py` — `record_initiated` self-transfer → non-retryable.
