## 1. Implementation

- [x] 1.1 Add an `asyncio.Lock` to `ReadModels`; wrap `catch_up()`'s drain in
  `async with self._lock`.

## 2. Tests

- [x] 2.1 `test_projections.py`: a store whose `read_all` yields (`await asyncio.sleep(0)`),
  seeded with a deposit; two concurrent `balance_of` calls via `asyncio.gather` return
  the single (not doubled) balance. (Fails without the lock.)

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit` green.
- [x] 3.3 `openspec validate fix-projection-catchup-race --strict` passes.
