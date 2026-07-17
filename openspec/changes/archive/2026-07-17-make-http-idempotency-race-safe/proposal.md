## Why

The `Idempotency-Key` handling has a check-then-act race and ignores the request
body. `create_transfer` does `recall` → mint a fresh `transfer_id` →
`await gateway.start(...)` → `remember`; two concurrent requests with the same key
both miss `recall`, mint **different** transfer ids, and start **two** workflows —
exactly the duplicate the key is meant to prevent. Separately, `remember` uses
`setdefault`, so reusing a key with a *different* body silently replays the first
response instead of rejecting the mismatch, violating the Idempotency-Key
contract.

## What Changes

- Replace check-then-act with an **atomic claim**: the first request for a key
  atomically reserves it (recording a request fingerprint) before doing any work;
  a concurrent second request for the same in-flight key is rejected as a
  duplicate-in-progress rather than starting a second operation.
- **Fingerprint the request**: a completed key replays its stored response only
  when the new request matches; a same-key/different-request is rejected with
  `409`/`422` instead of a wrong replay.
- Keep the store contract storage-agnostic so the Postgres-backed, TTL'd version
  is a drop-in later (single-process in-memory today; the claim semantics map
  directly onto `INSERT ... ON CONFLICT DO NOTHING`).

## Capabilities

### New Capabilities

- `idempotency`: HTTP-level request de-duplication via `Idempotency-Key` — atomic
  claim, request fingerprinting, first-response replay, and duplicate/mismatch
  rejection.

## Impact

- Code: `src/ledger/api/idempotency.py` (claim/complete API + entry states),
  `src/ledger/api/routers/transfers.py` (claim before work, complete after).
- Tests: `tests/unit/test_api.py` — concurrent same-key requests start the saga
  once; replay returns the stored response; same-key/different-body is rejected.
- No change to the wire schema of the success response.
