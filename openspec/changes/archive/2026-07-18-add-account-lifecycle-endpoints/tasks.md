## 1. Endpoints

- [x] 1.1 `POST /api/accounts/{id}/freeze`: load (404 if unknown), `account.freeze()`,
  save with correlation=account_id + traceparent, return the account.
- [x] 1.2 `POST /api/accounts/{id}/close`: same shape with `account.close()`.

## 2. Tests

- [x] 2.1 `test_api.py`: freeze an open account → frozen; freezing again → 409
  (invalid_transition); close an empty account → closed; closing a funded account
  → 409 (account_not_empty).

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit` green.
- [x] 3.3 `openspec validate add-account-lifecycle-endpoints --strict` passes.
