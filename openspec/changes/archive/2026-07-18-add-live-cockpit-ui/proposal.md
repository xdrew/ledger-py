## Why

The playground shows a transfer's saga, but the system's real story — that *every*
state change is an immutable event appended to one ordered global log, and that
sagas, accounts, projections, and the outbox all revolve around that log — is
invisible. For a portfolio piece the page should make the machinery legible: you
should *watch* the log grow, see the saga emit events into it, and see money move
between the available/held buckets. This turns the page from a form into a live
view of the architecture.

## What Changes

- Add `GET /api/events` — a global event feed (`from_position`, `limit`) so the
  page can stream the append-only log as it grows.
- Rebuild the playground into a **live cockpit**: a streaming event-log spine, a
  saga stage that highlights the current step and flashes the event it emits, an
  accounts panel showing available vs held balances as bars, and a read-side panel
  showing the log head the projections tail. Keep it a single self-contained page
  and preserve the existing flows (open/deposit/transfer/freeze/resolve).

## Capabilities

### Modified Capabilities

- `showcase`: the playground becomes a live cockpit and exposes a global event feed
  it streams to visualize the append-only log, the saga, accounts, and the read side.

## Impact

- Code: new `src/ledger/api/routers/events.py` (`GET /api/events`, api-key auth),
  wired in `main.py`; rebuilt `src/ledger/showcase/playground.html`.
- Consumes existing endpoints plus the new feed; no domain/store changes.
- Verify live against a running stack; the self-contained playground test still passes.
