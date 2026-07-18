## 1. Implementation

- [x] 1.1 In `accounts.py`, add an `Idempotency-Key` header to `deposit`; compute a
  fingerprint over account id + amount + currency; claim before crediting.
- [x] 1.2 Map claim results: `NEW` → credit then `complete`; `REPLAY` → return the
  stored response; `IN_PROGRESS` → `409`; `MISMATCH` → `422`. Release the claim if
  the credit fails.

## 2. Tests

- [x] 2.1 `test_api.py`: two deposits with the same key + body credit once and the
  second replays; a different amount with the same key → `422`, credited once;
  deposits without a key still work.

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit` green.
- [x] 3.3 `openspec validate make-deposit-idempotent --strict` passes.
