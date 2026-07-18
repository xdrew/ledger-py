## 1. Implementation

- [x] 1.1 Use a persistent demo source/destination across runs; first run arms a fresh
  source for one payment, later runs reuse it as-is.
- [x] 1.2 Add a Fund source control that deposits one payment into the demo source.
- [x] 1.3 Adaptive verdict: one settled → OCC prevented double-spend; zero settled →
  source is empty, re-arm by funding.

## 2. Verify

- [x] 2.1 Live: run 1 → one wins; run 2 (drained) → both rejected; Fund source → run 3
  wins again.
- [x] 2.2 `uv run pytest tests/unit` green (self-contained playground test passes).
- [x] 2.3 `openspec validate double-spend-persistent-source --strict` passes.
