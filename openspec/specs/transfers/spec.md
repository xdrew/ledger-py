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
`Initiated` state.

#### Scenario: Initiating a transfer

- **WHEN** a transfer of `100 USD` is initiated from account A to account B
- **THEN** a `TransferInitiated` event is recorded and the transfer is in the `Initiated` state

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
state, restoring the source's available balance so no money is moved.

#### Scenario: Posting fails after the hold

- **WHEN** a transfer's journal posting fails after the source hold was placed
- **THEN** the hold on the source is released and the transfer reaches `Failed`
- **AND** the source's available balance is restored and no money is moved

### Requirement: A residual credit failure parks for reconciliation

The system SHALL, when the destination credit fails *after* the source debit has
applied (the hold is already consumed and money has left the source), NOT record a
false `Failed` state. After exhausting retries the workflow SHALL park the transfer in
the `needs_reconciliation` state — durable and visible in the Temporal UI — recording
`TransferParkedForReconciliation`.

#### Scenario: Credit fails after the debit

- **WHEN** a transfer's source debit succeeds but the destination credit cannot complete
- **THEN** the transfer reaches `needs_reconciliation` (not `Failed`)
- **AND** the source has been debited and the destination has not been credited
- **AND** the transfer stream records the parked state for an operator to reconcile

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
