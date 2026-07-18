## Why

`ReadModels.catch_up()` drains the projection runner with no mutual exclusion. The
balances projection applies events with `available += amount` (not idempotent). Two
concurrent reads (`GET /balance` and/or `/statement`) both load the same checkpoint,
both `await store.read_all(...)` (which yields on a real Postgres store), both get the
same batch, and both apply it — **permanently double-counting** balances and
duplicating statement lines. The bug is invisible to the current tests because the
in-memory store's `read_all`/`project` have no internal `await`, so a drain runs to
completion without yielding; only a store that actually yields (Postgres) triggers it.

## What Changes

- Guard `catch_up()` with an `asyncio.Lock` so at most one drain runs at a time;
  concurrent readers serialize and each sees a consistent, non-double-counted model.
- Add a regression test using a store whose `read_all` yields, driving two concurrent
  catch-ups and asserting the projection is applied exactly once.

## Capabilities

### Modified Capabilities

- `projections`: catching up on read is concurrency-safe — overlapping reads never
  double-apply events.

## Impact

- Code: `src/ledger/projections/read_models_service.py` (lock around `catch_up`).
- Tests: `tests/unit/test_projections.py` — concurrent catch-up applies each event once
  (fails without the lock).
