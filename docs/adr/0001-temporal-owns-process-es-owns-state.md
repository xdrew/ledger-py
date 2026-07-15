# ADR-0001: Temporal owns the process, the event store owns the state

- Status: accepted
- Date: 2026-07-15

## Context

The PHP `ledger-core` orchestrated transfers with a hand-written synchronous
`TransferOrchestrator`, plus bespoke machinery for at-least-once delivery
(outbox relay), retries, and idempotency. It also event-sourced every aggregate,
including `Transfer`.

The rewrite adopts Temporal for durable execution. This raises a boundary
question: if Temporal already provides durable state and retries, do we still
event-source anything?

## Decision

Split ownership along process vs. state:

- **Temporal owns the process.** The transfer lifecycle (hold → post → settle,
  retries, compensation, timers) lives in a Temporal **workflow**. Temporal's
  event history is the durable execution log; workflow crashes resume, activities
  retry per policy, and stuck sagas are visible in the Temporal UI.
- **The event store owns the state.** Accounts (balances) and the Ledger
  (double-entry journal) remain **event-sourced** in Postgres, with
  `UNIQUE(stream_type, stream_id, version)` as the optimistic-concurrency guard.
  This append-only log is the system of record for money.

Activities are the only side-effect boundary. They call into the domain to
append account/journal events, and they also append **transfer** domain events
(`TransferInitiated/Held/Posted/Completed/Failed`) to the same event store — not
for durability (Temporal owns that) but for the audit trail, read-model
projections, and the showcase event-flow view.

## Consequences

- The outbox relay is no longer needed for *internal* reliability. It remains
  only to publish the event log to *external* consumers.
- Command-level idempotency is largely handled by deterministic `workflow_id`
  (`transfer-{id}`) + reuse policy. HTTP `Idempotency-Key` stays as a separate,
  transport-level dedup layer.
- `Transfer` is no longer the durability source — but we keep its projected
  event stream so the audit/read/showcase surfaces are unchanged for consumers.
- Two systems of record must not drift: activities must be idempotent and must
  append domain events transactionally with their state mutation.
