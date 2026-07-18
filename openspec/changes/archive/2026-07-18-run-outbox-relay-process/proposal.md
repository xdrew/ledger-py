## Why

The `OutboxRelay` tails the event log and republishes it to external consumers,
but nothing runs it: there is no process, and its checkpoint store is in-memory,
so even if started it would re-publish the whole log on every restart. The
"reliable external event publication" capability is wired but never runs.

## What Changes

- Add a **durable Postgres checkpoint store** (backed by the existing
  `relay_checkpoints` table) so the relay resumes from where it left off across
  restarts.
- Add a **continuous relay loop** that drains the relay and waits, repeatedly,
  until cancelled — with clean shutdown.
- Add a `ledger-relay` entrypoint that wires the event store, the Postgres
  checkpoint, and the `pg_notify` publisher and runs the loop.
- Semantics stay at-least-once (the checkpoint advances only after publishing), so
  downstream consumers must dedupe — as already documented.

## Capabilities

### New Capabilities

- `outbox`: a relay process republishes the event log to external consumers in
  global order, at least once, resuming from a durable checkpoint.

## Impact

- Code: new `PostgresCheckpointStore` (`src/ledger/projections/pg_checkpoints.py`),
  a `run_relay` loop in `src/ledger/outbox/relay.py`, and a `ledger-relay`
  entrypoint (`src/ledger/outbox/main.py`); `pyproject.toml` script.
- Tests: `run_relay` publishes appended events and exits cleanly on cancel (unit,
  in-memory); the Postgres checkpoint round-trips (integration, docker-gated).
