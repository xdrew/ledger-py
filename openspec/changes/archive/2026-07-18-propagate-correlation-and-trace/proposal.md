## Why

Event metadata carries `correlation_id`, `causation_id`, and `traceparent`, the
store persists and rehydrates them, and `project.md` lists correlation/trace
propagation as a cross-cutting requirement — but nothing ever populates them.
Every `repository.save` defaults to `EventMetadata.empty()`, so every persisted
event has a blank envelope. The audit-trail and distributed-tracing story is
wired but unfed.

## What Changes

- Thread a **correlation id** and a **W3C `traceparent`** from the HTTP request
  into the events a request produces:
  - The transfer saga uses the `transfer_id` as the correlation id (tying the
    account holds/debits/credits, the journal entry, and the transfer milestones
    of one transfer together across streams) and carries the request's
    `traceparent` through the workflow into every activity's `save`.
  - The account endpoints (open, deposit) tag their events with the account id as
    correlation id and the request's `traceparent`.
- Carry `traceparent` on `TransferInput` so it survives the workflow/activity
  boundary via the pydantic data converter.

Out of scope: full OpenTelemetry span propagation into Temporal via interceptors —
this change populates the event-log metadata the store already models; span-level
propagation can build on it.

## Capabilities

### New Capabilities

- `observability`: correlation and trace context are propagated from an incoming
  request through the saga and recorded in the event metadata of the events that
  request produces.

## Impact

- Code: `src/ledger/temporal/messages.py` (`traceparent` on `TransferInput`),
  `src/ledger/temporal/activities/transfer_activities.py` (build metadata, pass to
  every `save`), `src/ledger/api/routers/transfers.py` and `.../accounts.py`
  (read `traceparent`, set correlation id, pass metadata), `src/ledger/api/gateway.py`
  (carry traceparent into the workflow input).
- Tests: metadata is populated on the transfer's events (correlation = transfer id,
  traceparent preserved) and on account events.
