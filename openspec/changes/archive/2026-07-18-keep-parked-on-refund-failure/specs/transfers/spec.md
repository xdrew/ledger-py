## MODIFIED Requirements

### Requirement: Parked transfers are resolved by operator decision

The system SHALL let an operator resolve a parked (`needs_reconciliation`) transfer
by signalling one of two decisions, and SHALL drive the transfer to a truthful
terminal state accordingly. A **refund-source** decision SHALL credit the debited
amount back to the source account's available balance (via a deterministic,
idempotent operation id), record `TransferReconciled`, and reach the `Reconciled`
state. A **retry-credit** decision SHALL re-attempt the destination credit; on
success the transfer SHALL reach `Completed` (recording `TransferCompleted`), and on
continued failure it SHALL remain parked and await a further decision. If a
resolution attempt itself fails (a refund or retry activity errors), the transfer
SHALL remain parked and awaiting a further decision rather than failing the
workflow. The transfer aggregate SHALL permit `NeedsReconciliation → Reconciled` and
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

#### Scenario: A failed refund keeps the transfer parked

- **WHEN** a parked transfer is resolved with refund-source but the refund activity fails
- **THEN** the transfer remains in `needs_reconciliation` awaiting a further decision
- **AND** the workflow does not fail and can still be resolved by a subsequent decision
