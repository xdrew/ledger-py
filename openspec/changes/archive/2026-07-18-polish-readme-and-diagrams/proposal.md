## Why

The README sells the project in prose but has no visuals and no longer matches the
surface: it omits the newer endpoints (balance, freeze, close, resolve), the relay
process, the saga cockpit, and the design trade-offs a reviewer will want to see
named. For a portfolio piece the architecture and the saga should be legible at a
glance, and the hard decisions should be owned explicitly.

## What Changes

- Add Mermaid diagrams (rendered natively on GitHub, so no binary assets): a
  component/architecture diagram (Temporal-owns-process / event-store-owns-state,
  API, projections, outbox, worker, relay), a saga **state** diagram, and a saga
  **sequence** diagram including compensation and the parked/reconciliation path.
- Update the API surface list (accounts: balance / freeze / close; transfers:
  resolve) and the processes (`ledger-relay`), and mention the saga cockpit.
- Add a **Known trade-offs** section owning the deliberate decisions: gap-safe
  tailing via an append lock, in-memory-rebuilt projections, in-memory vs Postgres
  idempotency selection, and park-awaiting-operator.

## Capabilities

Documentation only — no requirement changes (archived with `--skip-specs`).

## Impact

- Files: `README.md`. No source or spec changes.
