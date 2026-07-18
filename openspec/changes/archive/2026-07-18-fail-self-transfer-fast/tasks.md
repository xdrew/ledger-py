## 1. API edge validation

- [x] 1.1 In `create_transfer`, raise `SameAccountTransfer` when
  `body.source_account_id == body.destination_account_id`, before the idempotency
  claim and before `gateway.start`.

## 2. Activity fast-fail

- [x] 2.1 In `record_initiated`, wrap `Transfer.initiate` and convert
  `SameAccountTransfer` / `InvalidAmount` into a non-retryable `ApplicationError`
  via `_terminal`.

## 3. Tests

- [x] 3.1 `test_api.py`: self-transfer POST → `422` (`same_account_transfer`),
  gateway not started.
- [x] 3.2 `test_transfer_activities.py`: `record_initiated` with a self-transfer
  raises a non-retryable `ApplicationError`.

## 4. Quality gate

- [x] 4.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 4.2 `uv run pytest tests/unit` green.
- [x] 4.3 `openspec validate fail-self-transfer-fast --strict` passes.
