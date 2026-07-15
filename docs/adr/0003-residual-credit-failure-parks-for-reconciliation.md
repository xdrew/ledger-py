# ADR-0003: A residual credit failure parks for reconciliation, never fakes a failure

- Status: accepted
- Date: 2026-07-15

## Context

The settle step debits the source, then credits the destination. Once the source
debit applies, the earlier hold is consumed — money has moved. If the
destination credit then fails, there is nothing left to cleanly compensate: the
funds have already left the source.

## Decision

Model the saga so that:

- Failures **before** the source debit are fully compensated (release hold) and
  the transfer ends `Failed` with no partial effects.
- A failure **after** the source debit (residual credit failure) does **not**
  record a `Failed` state. The workflow retries the credit per policy; if it
  still cannot complete, the workflow **parks in a `needs_reconciliation`
  state** — durable and loudly visible in the Temporal UI — awaiting an operator
  or a reconciliation activity.

Recording `Failed` here would be a lie: money already moved. Reconciliation (the
ledger trial balance) is the mechanism of record for closing the gap.

## Consequences

- No silent money loss and no false-negative failures.
- Stuck sagas are a first-class, queryable state — matches the operational
  "stuck-saga runbook" from the PHP version, now backed by Temporal visibility.
- Requires a reconciliation path (operator signal and/or scheduled activity) to
  drive `needs_reconciliation` workflows to resolution.
