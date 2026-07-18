## ADDED Requirements

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
