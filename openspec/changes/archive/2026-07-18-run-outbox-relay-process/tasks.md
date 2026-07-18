## 1. Durable checkpoint

- [x] 1.1 Add `PostgresCheckpointStore` (`src/ledger/projections/pg_checkpoints.py`)
  implementing the `CheckpointStore` protocol via an upsert on a checkpoints table
  (default `relay_checkpoints`).

## 2. Relay loop

- [x] 2.1 Add `run_relay(relay, *, poll_seconds)` to `outbox/relay.py`: loop
  `drain` + sleep until cancelled, exiting cleanly on `CancelledError`.

## 3. Entrypoint

- [x] 3.1 Add `ledger-relay` (`src/ledger/outbox/main.py`) wiring the event store,
  `PostgresCheckpointStore`, and `PostgresNotifyPublisher`, running `run_relay`.
- [x] 3.2 Register the `ledger-relay` script in `pyproject.toml`.

## 4. Tests

- [x] 4.1 Unit: `run_relay` publishes appended events (spy publisher, in-memory
  store + checkpoint) and stops cleanly on cancel.
- [x] 4.2 Integration (docker-gated): `PostgresCheckpointStore` load/save
  round-trips and a fresh relay resumes after the durable checkpoint.

## 5. Quality gate

- [x] 5.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 5.2 `uv run pytest tests/unit` green.
- [x] 5.3 `openspec validate run-outbox-relay-process --strict` passes.
