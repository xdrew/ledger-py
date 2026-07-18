# projections Specification

## Purpose

The CQRS read side. A projection runner tails the global event log from a durable
checkpoint and feeds each event to projectors that maintain read models — account
balances and an ordered account statement. Projectors are replay-safe, so read models
are rebuildable from the event store.
## Requirements
### Requirement: Maintain an account balances read model

The system SHALL project account events into an account-balances read model holding,
per account, the currency and the available, reserved, and total balances, together
with the account's status.

#### Scenario: Balances reflect account activity

- **WHEN** an account is opened, `100 USD` is deposited, and `40 USD` is held, and the
  projector runs
- **THEN** the account's balances show available `60`, reserved `40`, and total `100`

#### Scenario: Balances reflect status changes

- **WHEN** an account is frozen and the projector runs
- **THEN** the account's balances row shows the `frozen` status

### Requirement: Maintain an ordered account statement read model

The system SHALL project an account's balance-moving events (deposits, holds,
releases, debits, credits) into a statement read model, ordered by global position,
with one entry per event.

#### Scenario: Statement lists entries in order

- **WHEN** an account has a deposit then a hold and the projector runs
- **THEN** the statement for that account lists the deposit before the hold, in
  global-position order

### Requirement: Projection is checkpointed and replay-safe

The projection runner SHALL process events in global-position order starting after a
stored checkpoint and SHALL advance the checkpoint as it goes, so re-running the runner
with no new events does not re-apply already-processed events.

#### Scenario: Re-running after catching up changes nothing

- **WHEN** the projection runner has caught up to the latest event and is run again with
  no new events
- **THEN** it processes zero events and the read models are unchanged

#### Scenario: The checkpoint advances to the head

- **WHEN** the runner drains all stored events
- **THEN** the checkpoint equals the latest event's global position

### Requirement: Read models are rebuildable from the event store

The system SHALL be able to rebuild a read model by replaying the event log from the
start against a fresh projector and checkpoint, producing state identical to the live
projection.

#### Scenario: Rebuild yields identical balances

- **WHEN** read models have been projected live and are then rebuilt by replaying from
  position 0 against a fresh projector
- **THEN** the rebuilt balances are identical to the balances before the rebuild

### Requirement: Projection lag is derivable from the checkpoint

The runner's checkpoint position relative to the latest stored global position SHALL
determine the projection lag — the number of unprocessed events — so lag is observable.

#### Scenario: Lag is zero once caught up

- **WHEN** the runner has processed every stored event
- **THEN** the difference between the latest global position and the checkpoint is zero

#### Scenario: Lag reflects unprocessed events

- **WHEN** new events are appended that the runner has not yet processed
- **THEN** the difference between the latest global position and the checkpoint equals
  the number of those unprocessed events

### Requirement: Account reads are served from the projections

The system SHALL serve account balance and statement reads from the projection read
models rather than from the write-side aggregate or a raw event-stream scan. Before
serving, the projections SHALL catch up to the latest event in the global log so a
read reflects all events that occurred before it (read-your-writes).

#### Scenario: Balance read reflects prior activity

- **WHEN** an account is opened and funded and its projection-backed balance is read
- **THEN** the returned balance reflects those events after the projection catches up

#### Scenario: Statement read is served from the projection

- **WHEN** an account with several balance-moving events has its statement read
- **THEN** the statement is produced from the projection read model, listing the entries
  in global-position order

