## MODIFIED Requirements

### Requirement: A residual credit failure parks for reconciliation

The system SHALL, when the destination credit fails *after* the source debit has
applied (the hold is already consumed and money has left the source), NOT record a
false `Failed` state. After exhausting retries the workflow SHALL park the transfer
in the `needs_reconciliation` state — durable and visible in the Temporal UI —
recording `TransferParkedForReconciliation`, and SHALL remain alive awaiting an
operator resolution rather than terminating at the parked state.

#### Scenario: Credit fails after the debit

- **WHEN** a transfer's source debit succeeds but the destination credit cannot complete
- **THEN** the transfer reaches `needs_reconciliation` (not `Failed`)
- **AND** the source has been debited and the destination has not been credited
- **AND** the transfer stream records the parked state for an operator to reconcile

#### Scenario: The parked saga stays alive and queryable

- **WHEN** a transfer has parked in `needs_reconciliation`
- **THEN** the workflow is still running and its status query reports `needs_reconciliation`
- **AND** it is waiting for an operator resolution signal rather than having returned

## ADDED Requirements

### Requirement: Parked transfers are resolved by operator decision

The system SHALL let an operator resolve a parked (`needs_reconciliation`) transfer
by signalling one of two decisions, and SHALL drive the transfer to a truthful
terminal state accordingly. A **refund-source** decision SHALL credit the debited
amount back to the source account's available balance (via a deterministic,
idempotent operation id), record `TransferReconciled`, and reach the `Reconciled`
state. A **retry-credit** decision SHALL re-attempt the destination credit; on
success the transfer SHALL reach `Completed` (recording `TransferCompleted`), and on
continued failure it SHALL remain parked and await a further decision. The transfer
aggregate SHALL permit `NeedsReconciliation → Reconciled` and
`NeedsReconciliation → Completed` and SHALL reject any other transition out of the
parked state.

#### Scenario: Refund resolution makes the source whole

- **WHEN** a parked transfer is resolved with the refund-source decision
- **THEN** the source account's available balance is credited back by the transfer amount
- **AND** the transfer reaches `Reconciled` and records `TransferReconciled`
- **AND** the destination account remains uncredited

#### Scenario: Retry-credit resolution completes the transfer

- **WHEN** a parked transfer is resolved with the retry-credit decision and the destination
  can now be credited
- **THEN** the destination is credited exactly once and the transfer reaches `Completed`
- **AND** the transfer records `TransferCompleted`

#### Scenario: Refund is idempotent under activity retry

- **WHEN** the refund activity for a parked transfer runs and is then retried with the same input
- **THEN** the source is credited back exactly once

#### Scenario: A retry-credit that still fails keeps the transfer parked

- **WHEN** a parked transfer is resolved with retry-credit but the destination still cannot be credited
- **THEN** the transfer remains in `needs_reconciliation` awaiting a further decision
- **AND** no `Completed` or `Reconciled` state is recorded
