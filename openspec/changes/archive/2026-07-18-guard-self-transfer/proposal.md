## Why

`Transfer.initiate` does not check that the source and destination differ. A
self-transfer is nonsensical but currently proceeds: it holds on the account,
posts a journal that debits and credits the *same* account (formally balanced),
settles both legs, and completes — emitting a full milestone stream for money
that only moved in a circle. A ledger's integrity rule is that a transfer moves
value *between* accounts; this should be rejected up front.

## What Changes

- `Transfer.initiate` rejects `source == destination` with a domain error before
  any event is recorded.
- Add a `SameAccountTransfer` domain error (`code: same_account_transfer`, mapped
  to `422`).

## Capabilities

### Modified Capabilities

- `transfers`: the initiate requirement is strengthened to require distinct
  source and destination accounts.

## Impact

- Code: `src/ledger/domain/transfers/transfer.py` (guard in `initiate`),
  `src/ledger/domain/shared/errors.py` (new error),
  `src/ledger/api/problem_details.py` (status mapping).
- Tests: `tests/unit/test_transfer.py` — self-transfer is rejected; a normal
  transfer still initiates.
