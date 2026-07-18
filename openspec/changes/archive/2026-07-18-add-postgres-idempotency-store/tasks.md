## 1. Protocol + in-memory (async)

- [x] 1.1 Define an async `IdempotencyStore` Protocol (`claim`/`complete`/`discard`).
- [x] 1.2 Rename the current class to `InMemoryIdempotencyStore` and make its methods
  async.

## 2. Postgres impl

- [x] 2.1 Add `PostgresIdempotencyStore` keyed by `(key, route)` with a fingerprint
  column and optional response; `claim` uses `INSERT ... ON CONFLICT DO NOTHING`
  then classifies; add its DDL to the schema (idempotent `CREATE TABLE IF NOT EXISTS`).

## 3. Wiring

- [x] 3.1 Select the implementation in context/factory (Postgres when DB URL set,
  else in-memory). Update `AppContext` typing and test fixtures.
- [x] 3.2 `await` claim/complete/discard in `transfers.py` and `accounts.py`.

## 4. Tests

- [x] 4.1 Unit: async in-memory claim lifecycle (new → in-progress → mismatch →
  replay; discard releases). Update existing idempotency tests to `await`.
- [x] 4.2 Integration (docker-gated): Postgres claim atomicity (two claims → one
  new), replay after complete, mismatch, discard.

## 5. Quality gate

- [x] 5.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 5.2 `uv run pytest tests/unit` green.
- [x] 5.3 `openspec validate add-postgres-idempotency-store --strict` passes.
