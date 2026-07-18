## 1. Implementation

- [x] 1.1 Add `SameAccountTransfer(DomainError)` with `code =
  "same_account_transfer"` in `errors.py`.
- [x] 1.2 In `Transfer.initiate`, raise it when `source_account_id ==
  destination_account_id`, before recording the event.
- [x] 1.3 Map `same_account_transfer → 422` in `problem_details.py`.

## 2. Tests

- [x] 2.1 `test_transfer.py`: a self-transfer raises; a normal transfer still
  initiates with `TransferInitiated`.

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest` green.
- [x] 3.3 `openspec validate guard-self-transfer --strict` passes.
