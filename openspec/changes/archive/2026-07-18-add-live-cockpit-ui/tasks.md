## 1. Global event feed

- [x] 1.1 Add `GET /api/events` (`from_position`, `limit`, api-key auth) returning
  compact global events (position, stream type, event type, stream id, time) via
  `store.read_all`; wire the router in `main.py`.

## 2. Cockpit UI

- [x] 2.1 Rebuild `playground.html` as a live cockpit: streaming event-log spine,
  saga stage (current step highlighted + emitted-event flash), accounts panel
  (available/held bars), read-side panel (log head). Self-contained, theme per the
  design plan; preserve open/deposit/transfer/freeze/resolve flows.

## 3. Verify & gate

- [x] 3.1 Drive live against a running stack (worker + api): opening/depositing and
  running a transfer stream events into the log; the saga stage advances; balances
  move; a frozen destination shows the parked path and resolves.
- [x] 3.2 `uv run pytest` green (self-contained playground test still passes).
- [x] 3.3 `openspec validate add-live-cockpit-ui --strict` passes.
