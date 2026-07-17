## Why

Projections and the outbox relay tail the global event log with
`WHERE global_position > cursor ORDER BY global_position` and advance the
checkpoint to the last position seen. But `global_position` is a Postgres
`IDENTITY` value assigned at `INSERT` time, while a row only becomes visible at
`COMMIT`. Under concurrent appends a transaction that was assigned a *lower*
position can commit *after* a higher-position row has already been consumed and
the checkpoint advanced past it — so the lower-position event is never read.
That is a silent loss of events for read models and external consumers: the
store's own docstrings promise "gap-free ordering" and "at-least-once", but
today it delivers at-most-once with holes whenever writes overlap. For a system
whose entire mandate is correctness of money under concurrency, this is the most
important latent defect, and it is currently untested (all suites are
single-writer).

## What Changes

- Make `global_position` **commit-ordered and gap-safe for consumers**: a
  committed event is never observable at a position lower than one a consumer has
  already passed. Achieved by serializing position assignment with a
  transaction-scoped Postgres advisory lock held across the append so position
  order equals commit order.
- Guarantee that a cursor-based tail (projections + outbox) observes **every**
  committed event exactly once, with no dependency on writer concurrency.
- Add a concurrency regression test (real Postgres via testcontainers) that
  drives overlapping appends and asserts a tailing consumer sees the full set
  with monotonic, non-regressing positions.
- Document the throughput tradeoff and the considered alternative (xmin/xact-id
  visibility horizon) in `design.md`.

## Capabilities

### Modified Capabilities

- `event-store`: the global-ordering requirement is strengthened from
  "monotonically increasing positions" to "commit-ordered, gap-safe consumption"
  — a new normative guarantee that cursor tailing never skips a committed event
  under concurrent writers.

## Impact

- Code: `src/ledger/eventstore/postgres.py` (append path), `schema.py` (no table
  change required; advisory-lock key is a constant). In-memory store already
  serializes within the event loop and satisfies the guarantee unchanged.
- Consumers unchanged: `projections/runner.py` and `outbox/relay.py` become
  correct without modification once positions are commit-ordered.
- Tests: new `tests/integration/test_postgres_store.py` concurrency case.
- Performance: appends are globally serialized (documented, acceptable for the
  system-of-record log; the money-correctness mandate outranks write throughput).
