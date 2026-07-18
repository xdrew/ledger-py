## Why

The HTTP idempotency store is in-memory and per-process, so with more than one API
worker the same `Idempotency-Key` can start two operations (each worker has its own
map) and keys are lost on restart. For a money API this undermines the guarantee
the key exists to provide. The store needs a durable, shared backing — the same
shape the event store already uses (a protocol with in-memory and Postgres
implementations).

## What Changes

- Define an **async `IdempotencyStore` protocol** (`claim` / `complete` /
  `discard`) and make the in-memory store implement it (async).
- Add a **Postgres implementation** keyed by `(key, route)` with a fingerprint
  column: `claim` inserts atomically (`ON CONFLICT DO NOTHING`) so concurrent
  duplicates across workers resolve to exactly one `NEW`; the rest classify as
  `REPLAY` / `IN_PROGRESS` / `MISMATCH`.
- Select the implementation via the existing store factory (Postgres when a
  database URL is configured, else in-memory).
- **BREAKING** (internal): `claim`/`complete`/`discard` become async; the transfer
  and deposit routers `await` them.

## Capabilities

### Modified Capabilities

- `idempotency`: the store is durable and shared across workers, not just
  in-process.

## Impact

- Code: `src/ledger/api/idempotency.py` (async protocol + async in-memory + Postgres
  impl + schema), `src/ledger/api/context.py` and the store factory (select impl),
  routers `transfers.py` / `accounts.py` (`await`).
- Tests: in-memory async claim lifecycle (unit); Postgres claim atomicity and
  replay (integration, docker-gated).
