## Why

The FastAPI `lifespan` builds the runtime context on startup (opening an asyncpg
pool) but only `yield`s — it never releases those resources on shutdown. Each
restart leaks the connection pool; there is no graceful shutdown. A production
service should close what it opened.

## What Changes

- `lifespan` closes the resources it owns on shutdown: when it built the context
  (i.e. tests did not inject one), it closes the event-store pool.
- Add `AppContext.aclose()` that closes the store if the implementation exposes a
  close (Postgres pool); the in-memory store is a no-op.
- Only the context the lifespan itself created is closed — a test-injected
  context is left untouched.

## Capabilities

### Modified Capabilities

- `api`: add a requirement that the application releases the resources it opened
  on shutdown.

## Impact

- Code: `src/ledger/api/main.py` (lifespan try/finally), `src/ledger/api/context.py`
  (`AppContext.aclose`).
- Tests: `tests/unit/test_api.py` — an owned context is closed on shutdown; an
  injected one is not.
