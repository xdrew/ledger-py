## Why

The playground can start a transfer and poll its status as a pill plus a raw JSON
blob, but it never shows the transfer *as a saga*: the lifecycle it moves through,
the events it emits, or — now that reconciliation exists — the operator decision a
parked transfer is waiting for. The project's whole pitch is a durable-execution
saga with visible, resolvable stuck states; the showcase should make that legible
at a glance instead of hiding it behind `JSON.stringify`.

## What Changes

- Render the transfer as a **lifecycle stepper**: `Initiated → Held → Posted →
  Completed`, with the branch states `Failed` and `NeedsReconciliation →
  Reconciled` shown distinctly (done / current / pending / error / parked).
- Render the transfer's **event timeline** from `GET /api/transfers/{id}/events`
  (event type, version, global position, time), so the audit stream is visible.
- When a transfer is `needs_reconciliation`, show **resolve controls** — "Refund
  source" and "Retry credit" — that call `POST /api/transfers/{id}/resolve` and
  then keep polling to show the resulting `Reconciled`/`Completed` transition.
- Keep it a single self-contained HTML file (no external assets), consistent with
  the existing playground's look; extend, don't replace, the current flow.

## Capabilities

### New Capabilities

- `showcase`: the self-contained playground page — drives the live API and
  visualizes a transfer saga (lifecycle stepper, event timeline, reconciliation
  resolve controls).

## Impact

- Code: `src/ledger/showcase/playground.html` (markup, styles, and vanilla-JS
  rendering of the stepper, timeline, and resolve controls).
- No server code changes: consumes existing endpoints plus the resolve endpoint
  added in `add-transfer-resolve-endpoint`.
- Test: the existing `test_api.py` playground-served check still passes; the page
  stays self-contained.
