## 1. Read-model container

- [x] 1.1 Add a `ReadModels` container in `src/ledger/projections/` holding the
  balances + statement projections and a `ProjectionRunner` over them with an
  in-memory checkpoint; expose `catch_up()` (drain) and accessors
  `balance_of(id)` / `statement_of(id)`. Add a `build_read_models(store, registry)`.

## 2. Context wiring

- [x] 2.1 `AppContext` gains a `read_models: ReadModels` field; `build_runtime_context`
  builds it. Update test fixtures/constructors.

## 3. API

- [x] 3.1 Add `GET /api/accounts/{id}/balance` served from the balances projection
  after `catch_up()` (404 if unknown).
- [x] 3.2 Serve `GET /api/accounts/{id}/statement` from the statement projection
  after `catch_up()` instead of scanning the raw stream.

## 4. Tests

- [x] 4.1 `test_api.py`: after open + deposit + (a transfer or hold), the
  projection-backed balance reflects the activity; the statement lists entries in
  order — both served from the projection.

## 5. Quality gate

- [x] 5.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 5.2 `uv run pytest tests/unit` green.
- [x] 5.3 `openspec validate serve-projection-read-models --strict` passes.
