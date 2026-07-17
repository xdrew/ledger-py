## 1. Store

- [x] 1.1 Rework `src/ledger/api/idempotency.py`: entry with `fingerprint` +
  optional `response`; `claim(key, route, fingerprint) -> (ClaimResult, response?)`
  with results `NEW | IN_PROGRESS | MISMATCH | REPLAY`; `complete(...)` to record
  the response; `discard(...)` to release a reservation on failure. `claim`
  performs no `await` (atomic under the event loop).

## 2. Route wiring

- [x] 2.1 In `transfers.py`, compute a request fingerprint (sha256 over canonical
  body) and `claim` before minting the transfer id / starting the saga.
- [x] 2.2 Map results: `NEW` → start, then `complete`; `REPLAY` → return stored
  response; `IN_PROGRESS` → `409` problem-details; `MISMATCH` → `422`
  problem-details. Release the claim (`discard`) if `gateway.start` raises.

## 3. Tests

- [x] 3.1 Concurrent same-key requests (`asyncio.gather`, fake gateway counting
  `start`): assert `start` runs once and the duplicate is rejected/replayed, never
  a second saga.
- [x] 3.2 Replay: same key + same body → identical response, one `start`.
- [x] 3.3 Mismatch: same key + different body → `422`, no second `start`.
- [x] 3.4 No-key requests unaffected.

## 4. Quality gate

- [x] 4.1 `ruff check` + `ruff format --check` + `pyright` (strict) clean.
- [x] 4.2 `uv run pytest` green.
- [x] 4.3 `openspec validate make-http-idempotency-race-safe --strict` passes.
