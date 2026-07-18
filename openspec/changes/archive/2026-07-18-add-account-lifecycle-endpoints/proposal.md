## Why

The `Account` aggregate supports freezing and closing, but the HTTP API exposes
only open and deposit — an operator cannot take an account out of service through
the API. This also blocks a realistic showcase: a residual credit failure (the
parked-transfer path) requires a destination that becomes uncreditable, which
freezing an account produces.

## What Changes

- Add `POST /api/accounts/{id}/freeze` (open → frozen) and
  `POST /api/accounts/{id}/close` (empty account → closed).
- Invalid transitions map to `409` via the existing problem-details handler
  (freezing a non-open account → `invalid_transition`; closing a non-empty
  account → `account_not_empty`).
- Events are tagged with the account id as correlation id and the request's
  traceparent, consistent with open/deposit.

## Capabilities

### Modified Capabilities

- `accounts`: the freeze/close lifecycle is exposed through the HTTP API.

## Impact

- Code: `src/ledger/api/routers/accounts.py` (two endpoints).
- Tests: `tests/unit/test_api.py` — freeze an open account; freezing a frozen one
  is `409`; close an empty account; closing a non-empty one is `409`.
