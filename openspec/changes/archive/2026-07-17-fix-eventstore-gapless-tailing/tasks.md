## 1. Implementation

- [x] 1.1 Add a namespaced `bigint` advisory-lock key constant in
  `src/ledger/eventstore/postgres.py` (documented; not reused elsewhere).
- [x] 1.2 In `PostgresEventStore.append`, take `pg_advisory_xact_lock(<key>)` as
  the first statement inside the existing transaction, before the `MAX(version)`
  read and the inserts, so it is held until commit.
- [x] 1.3 Confirm the in-memory store already satisfies gap-safe consumption
  (single-threaded event-loop serialization); add a brief comment noting the
  guarantee it relies on.

## 2. Tests

- [x] 2.1 Add an integration test in `tests/integration/test_postgres_store.py`:
  concurrently append many events across several streams with
  `asyncio.gather`, then drain a tailing consumer and assert it observed exactly
  the appended count, in strictly increasing global-position order, with every
  event id present.
- [x] 2.2 Add an ordering-invariant assertion: after concurrent appends,
  `read_all` returns positions strictly ascending with no committed event missing.

## 3. Quality gate

- [x] 3.1 `uv run ruff check src tests` and `uv run ruff format --check src tests`.
- [x] 3.2 `uv run pyright` (strict) clean.
- [x] 3.3 `uv run pytest` green (unit + integration).
- [x] 3.4 `openspec validate fix-eventstore-gapless-tailing --strict` passes.
