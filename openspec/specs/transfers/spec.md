# transfers Specification

## Purpose

Money movement between two accounts, run as a **Temporal workflow saga**: hold on
the source → post a balanced journal entry → settle (debit source, credit
destination). Temporal owns the *process* (durable execution, retries,
compensation); the `Transfer` aggregate records each milestone as the *audit/read*
stream. The saga is safe under partial failure: it compensates before the debit and
parks for reconciliation after it.
## Requirements
### Requirement: Initiate a transfer

The system SHALL initiate a transfer between a source and destination account for a
positive amount, recording `TransferInitiated` and placing the transfer in the
`Initiated` state. The source and destination accounts MUST be different; a
transfer whose source equals its destination SHALL be rejected before any event is
recorded. The API SHALL reject a self-transfer at request time with a `422` before
starting the saga, and the initiate activity SHALL treat a self-transfer as a
non-retryable failure (it is not a transient error to retry).

#### Scenario: Initiating a transfer

- **WHEN** a transfer of `100 USD` is initiated from account A to account B
- **THEN** a `TransferInitiated` event is recorded and the transfer is in the `Initiated` state

#### Scenario: A self-transfer is rejected at the API

- **WHEN** a transfer request has the same source and destination account
- **THEN** the API rejects it with `422` and does not start the saga

#### Scenario: A self-transfer that reaches the activity fails fast

- **WHEN** the initiate activity is run for a self-transfer
- **THEN** it fails with a non-retryable error rather than being retried as transient

### Requirement: Complete a transfer on the happy path

The system SHALL, for a fully funded transfer, place a hold on the source, post a
balanced double-entry journal entry (debit source / credit destination), settle the
balances (debit the source's held funds, credit the destination), and reach the
`Completed` state — recording `TransferHeld`, `TransferPosted`, and `TransferCompleted`.

#### Scenario: A funded transfer completes and moves the money

- **WHEN** account A has `100 USD` available and a transfer of `100 USD` from A to B is run
- **THEN** the transfer reaches `Completed`
- **AND** account A's total decreases by `100 USD` and account B's available increases by `100 USD`
- **AND** a journal entry debiting A and crediting B by `100 USD` is posted

### Requirement: Insufficient funds fail at the hold with no partial effects

The system SHALL fail a transfer at the hold step when the source has insufficient
available funds, leaving no partial effects: no hold, no journal entry, and unchanged
balances, reaching the `Failed` state with an insufficient-funds reason.

#### Scenario: Transfer with insufficient funds

- **WHEN** a transfer of `150 USD` is run from account A which has only `100 USD` available
- **THEN** the transfer reaches `Failed` with reason `insufficient_funds`
- **AND** no hold is placed, no journal entry is posted, and A's and B's balances are unchanged

### Requirement: A failure before the debit is compensated

The system SHALL, when a transfer fails after the hold is placed but before the source
debit (for example the journal posting fails), release the hold and reach the `Failed`
state, restoring the source's available balance so no money is moved. When a journal
entry had already been posted before the compensating failure, the system SHALL also
post a reversing journal entry (the original entry's debit and credit legs swapped) so
the ledger nets to zero for that transfer — the write-once original is never deleted,
it is reversed.

#### Scenario: Posting fails after the hold

- **WHEN** a transfer's journal posting fails after the source hold was placed
- **THEN** the hold on the source is released and the transfer reaches `Failed`
- **AND** the source's available balance is restored and no money is moved

#### Scenario: A debit failure after posting reverses the journal

- **WHEN** the source debit fails after the journal entry was posted, and the transfer is compensated
- **THEN** the hold is released, the source balance is restored, and the transfer reaches `Failed`
- **AND** a reversing journal entry is posted so the original entry and its reversal net to zero

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

### Requirement: Transfer state transitions are enforced

The transfer aggregate SHALL permit only valid state transitions
(`Initiated → Held → Posted → Completed`; `→ Failed` from `Initiated`/`Held`/`Posted`;
`Posted → NeedsReconciliation`), and SHALL reject an attempt to advance from the wrong
state.

#### Scenario: Completing a transfer that was never posted is rejected

- **WHEN** a transfer in the `Held` state is asked to complete without having posted
- **THEN** the operation is rejected as an invalid transition

### Requirement: Saga steps are idempotent under retry and replay

Each saga step SHALL be idempotent: balance-moving activities carry a deterministic
`operation_id` derived from the transfer id and step, journal posting is keyed by a
deterministic entry id, and milestone recording is guarded by the transfer's current
status. Re-running any activity (a Temporal retry) or replaying the workflow SHALL NOT
double-apply an effect.

#### Scenario: Re-running the hold activity does not double-hold

- **WHEN** the hold activity for a transfer runs and is then retried with the same input
- **THEN** the source is held exactly once and the transfer is in the `Held` state

#### Scenario: Re-running the journal posting reuses the same entry

- **WHEN** the journal-posting activity for a transfer runs and is then retried
- **THEN** the same journal entry id is returned and no second entry is posted

### Requirement: Concurrent transfers from one source settle exactly once

The system SHALL settle exactly once when two transfers run concurrently from the same
source that has funds for only one: it completes one transfer, fails the other, and
debits the source only once — enforced by the event store's optimistic concurrency.

#### Scenario: Two concurrent transfers, funds for one

- **WHEN** account A has `100 USD` and two transfers of `100 USD` from A run concurrently
- **THEN** exactly one transfer reaches `Completed` and the other reaches `Failed`
- **AND** account A is debited exactly once

### Requirement: Temporal owns durable execution; the aggregate is the audit trail

The transfer process SHALL run as a Temporal workflow so that a worker crash resumes,
activities retry per policy, and stuck sagas are visible. The `Transfer` aggregate
SHALL record each milestone (`TransferInitiated/Held/Posted/Completed/Failed/
ParkedForReconciliation`) to the event store as the queryable audit trail; the
workflow SHALL expose the current status via a query.

#### Scenario: The audit stream mirrors the saga milestones

- **WHEN** a funded transfer runs to completion
- **THEN** its event stream contains `TransferInitiated`, `TransferHeld`,
  `TransferPosted`, and `TransferCompleted` in order

#### Scenario: Status is queryable while the saga runs

- **WHEN** a running transfer workflow is queried for its status
- **THEN** it returns the current saga state

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

### Requirement: Parked transfers are resolvable through the HTTP API

The API SHALL expose an operation to resolve a transfer that is in the
`needs_reconciliation` state by supplying an operator decision
(`refund_source` or `retry_credit`), which SHALL be delivered to the running
transfer workflow as its reconciliation signal. The API SHALL reject a resolve
request for a transfer that is not currently in `needs_reconciliation` with a
`409` conflict, and SHALL acknowledge an accepted resolution without waiting for
the workflow to reach its next terminal state.

#### Scenario: Resolving a parked transfer signals the workflow

- **WHEN** a resolve request with a valid decision is made for a transfer in `needs_reconciliation`
- **THEN** the decision is delivered to the transfer workflow as its reconciliation signal
- **AND** the API acknowledges the request as accepted

#### Scenario: Resolving a non-parked transfer is rejected

- **WHEN** a resolve request is made for a transfer that is not in `needs_reconciliation`
- **THEN** the request is rejected with a `409` conflict
- **AND** no reconciliation signal is sent

