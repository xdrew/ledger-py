## 1. Implementation

- [x] 1.1 In `_await_resolution`, wrap the `refund_source` activity call in
  `try/except ActivityError: continue` so a failed refund keeps the transfer parked
  (mirrors the retry-credit branch).

## 2. Tests

- [x] 2.1 `test_transfer_saga.py`: park, signal refund with a failing refund
  activity → status stays `needs_reconciliation` and the workflow is still running;
  then signal a working resolution → reaches its terminal state.

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit tests/integration/test_transfer_saga.py` green.
- [x] 3.3 `openspec validate keep-parked-on-refund-failure --strict` passes.
