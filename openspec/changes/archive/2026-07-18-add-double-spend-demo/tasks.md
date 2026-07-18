## 1. UI

- [x] 1.1 Add a "Concurrency · double-spend" section to `playground.html` with a run
  control and two result lanes plus a verdict + source balance.

## 2. Behavior

- [x] 2.1 On run: open a source funded for exactly one payment + a destination; fire
  two concurrent `POST /api/transfers` of that amount; poll each to a terminal state;
  render one `Completed` and one `Failed (insufficient_funds)`, the verdict, and the
  source's final balance (debited once).

## 3. Verify & gate

- [x] 3.1 Drive live: the double-spend yields exactly one completed and one rejected
  transfer; the source ends debited once.
- [x] 3.2 `uv run pytest tests/unit` green (self-contained playground test passes).
- [x] 3.3 `openspec validate add-double-spend-demo --strict` passes.
