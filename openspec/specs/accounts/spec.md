# accounts Specification

## Purpose

The account lifecycle aggregate: an event-sourced balance with two buckets —
`available` (spendable) and `reserved` (held pending settlement). It enforces the
money invariants (positive amounts, currency match, non-negative available, valid
state) and makes balance-moving operations idempotent under saga retries.

## Requirements

### Requirement: Open an account

The system SHALL open an account in a single currency with zero available and zero
reserved balance, emitting `AccountOpened`. An opened account is active (`Open`).

#### Scenario: Opening a new account

- **WHEN** an account is opened with currency `USD`
- **THEN** an `AccountOpened` event is recorded
- **AND** its available balance, reserved balance, and total are zero `USD`
- **AND** the account is `Open`

### Requirement: Deposit funds

An `Open` account SHALL accept a deposit of a positive amount in the account's
currency, increasing the available balance and emitting `FundsDeposited`.

#### Scenario: Depositing into an open account

- **WHEN** `100 USD` is deposited into an open `USD` account with zero balance
- **THEN** a `FundsDeposited` event is recorded
- **AND** the available balance is `100 USD` and the total is `100 USD`

### Requirement: Place a hold on available funds

An `Open` account SHALL place a hold for a positive amount not exceeding the
available balance, moving that amount from available to reserved and emitting
`FundsHeld`. A hold that exceeds available funds SHALL be rejected with no event.

#### Scenario: Holding within the available balance

- **WHEN** `40 USD` is held on an account with `100 USD` available
- **THEN** a `FundsHeld` event is recorded
- **AND** available is `60 USD`, reserved is `40 USD`, and the total is `100 USD`

#### Scenario: Holding more than available is rejected

- **WHEN** a hold of `150 USD` is attempted on an account with `100 USD` available
- **THEN** the operation fails with an insufficient-funds error
- **AND** no event is recorded and the balances are unchanged

### Requirement: Release a hold

An `Open` account SHALL release a hold for a positive amount not exceeding the
reserved balance, moving that amount from reserved back to available and emitting
`HoldReleased`. A release exceeding the reserved balance SHALL be rejected.

#### Scenario: Releasing a previously held amount

- **WHEN** `40 USD` is released on an account with `40 USD` reserved and `60 USD` available
- **THEN** a `HoldReleased` event is recorded
- **AND** the available balance is `100 USD` and the reserved balance is `0 USD`

#### Scenario: Releasing more than reserved is rejected

- **WHEN** a release of `50 USD` is attempted on an account with `40 USD` reserved
- **THEN** the operation fails with an insufficient-funds error and no event is recorded

### Requirement: Debit draws from the reserved bucket

An `Open` account SHALL finalize an outflow by debiting a positive amount not
exceeding the reserved balance, reducing reserved and emitting `AccountDebited`. A
debit consumes a prior hold; it SHALL be rejected if it exceeds the reserved balance.

#### Scenario: Debiting a held amount

- **WHEN** `40 USD` is debited on an account with `40 USD` reserved and `60 USD` available
- **THEN** an `AccountDebited` event is recorded
- **AND** the reserved balance is `0 USD` and the available balance is `60 USD`

#### Scenario: Debiting more than reserved is rejected

- **WHEN** a debit of `200 USD` is attempted on an account with `100 USD` reserved
- **THEN** the operation fails with an insufficient-funds error and no event is recorded

### Requirement: Credit increases available funds

An `Open` account SHALL receive an inflow by crediting a positive amount in the
account's currency, increasing available and emitting `AccountCredited`.

#### Scenario: Crediting an open account

- **WHEN** `100 USD` is credited to an open `USD` account
- **THEN** an `AccountCredited` event is recorded and available increases by `100 USD`

### Requirement: Balance-moving operations are idempotent by operation id

Each balance-moving operation (hold, release, debit, credit) SHALL carry an
`operation_id`. Applying an operation whose id has already been applied to the
account SHALL be a no-op that records no event and does not change balances, so a
replayed saga step (a Temporal activity retry) is safe.

#### Scenario: Replaying a hold with the same operation id is a no-op

- **WHEN** a hold of `40 USD` with a given operation id is applied, then applied again
  twice with the same operation id
- **THEN** only one `FundsHeld` event is recorded and reserved is `40 USD` (not `120 USD`)

### Requirement: Currency consistency

An account SHALL reject any operation whose amount currency differs from the
account's currency, with no event recorded.

#### Scenario: Depositing a mismatched currency is rejected

- **WHEN** a deposit in `EUR` is attempted on a `USD` account
- **THEN** the operation fails with a currency-mismatch error and no event is recorded

### Requirement: Operations require an open account

The account SHALL reject balance-moving operations unless it is `Open`; operating on
a `Frozen` or `Closed` account fails with no event.

#### Scenario: Depositing into a frozen account is rejected

- **WHEN** an account is frozen and a deposit is attempted
- **THEN** the operation fails with an account-not-active error and no event is recorded

### Requirement: Freeze and close transitions

An `Open` account SHALL be freezable (`Open → Frozen`, emitting `AccountFrozen`) and
closable when empty (`Open`/`Frozen → Closed`, emitting `AccountClosed`). Closing a
non-empty account SHALL be rejected; an illegal status transition (e.g. freezing a
frozen account, closing a closed account) SHALL be rejected.

#### Scenario: Closing an empty account

- **WHEN** an open account with zero available and zero reserved is closed
- **THEN** an `AccountClosed` event is recorded and the account is `Closed`

#### Scenario: Closing a non-empty account is rejected

- **WHEN** a close is attempted on an account holding a non-zero balance
- **THEN** the operation fails with an account-not-empty error and no event is recorded

### Requirement: Accounts rehydrate from their event stream

An account SHALL reconstruct its state (currency, status, available, reserved, and
applied operation ids) by replaying its persisted events, identical to the live
aggregate.

#### Scenario: Rehydrating an account

- **WHEN** an account is opened, deposited into, and held against, then saved and reloaded
- **THEN** the reloaded account has the same available, reserved, status, and version
