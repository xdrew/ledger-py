## Why

Deposit moves money but is not idempotent: a retried `POST
/api/accounts/{id}/deposit` (client timeout + retry) credits the account twice.
The transfer endpoint already supports `Idempotency-Key` via the race-safe claim
store; deposit should use the same mechanism.

## What Changes

- `POST /api/accounts/{id}/deposit` accepts an optional `Idempotency-Key`. The
  first call performs the deposit and records its response; a repeat with the same
  key and the same request replays it; a concurrent duplicate is rejected as
  in-progress (`409`); the same key with a different request (different account /
  amount / currency) is rejected (`422`).
- The request fingerprint covers the account id, amount, and currency.

## Capabilities

### Modified Capabilities

- `idempotency`: the `Idempotency-Key` mechanism also guards account deposits.

## Impact

- Code: `src/ledger/api/routers/accounts.py` (claim/complete around deposit).
- Tests: `tests/unit/test_api.py` — repeated deposit with a key credits once and
  replays; a different body with the same key is `422`.
