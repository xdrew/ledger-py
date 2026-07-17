## 1. Markup & styles

- [x] 1.1 Add a "Saga" card to `playground.html` with a lifecycle stepper region
  and an event-timeline region; extend the existing stylesheet (stepper node
  states: done / current / pending / error / parked; timeline rows). Keep the page
  self-contained (no external assets).

## 2. Behavior (vanilla JS)

- [x] 2.1 On transfer start and each poll, render the stepper from the transfer's
  status (map status → reached steps; show `Failed` / `NeedsReconciliation` /
  `Reconciled` branches distinctly).
- [x] 2.2 Fetch `GET /api/transfers/{id}/events` and render the timeline (type,
  version, global position, time) in order.
- [x] 2.3 When status is `needs_reconciliation`, show "Refund source" / "Retry
  credit" buttons that `POST /api/transfers/{id}/resolve` with the decision, then
  resume polling; hide the controls otherwise.
- [x] 2.4 Keep polling until a truly terminal state (`completed`, `failed`,
  `reconciled`); `needs_reconciliation` is awaiting an operator, so keep the view
  live and actionable there.

## 3. Verify & gate

- [x] 3.1 Drive the page against a running stack (worker + api): happy-path
  completes through the stepper; a parked transfer shows resolve controls and
  reaches `Reconciled`/`Completed` after resolving.
- [x] 3.2 `uv run pytest` green (playground-served test still passes).
- [x] 3.3 `openspec validate add-saga-cockpit-ui --strict` passes.
