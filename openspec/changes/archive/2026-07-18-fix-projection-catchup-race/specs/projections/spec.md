## MODIFIED Requirements

### Requirement: Account reads are served from the projections

The system SHALL serve account balance and statement reads from the projection read
models rather than from the write-side aggregate or a raw event-stream scan. Before
serving, the projections SHALL catch up to the latest event in the global log so a
read reflects all events that occurred before it (read-your-writes). Catching up SHALL
be serialized so that concurrent reads never apply the same event more than once.

#### Scenario: Balance read reflects prior activity

- **WHEN** an account is opened and funded and its projection-backed balance is read
- **THEN** the returned balance reflects those events after the projection catches up

#### Scenario: Statement read is served from the projection

- **WHEN** an account with several balance-moving events has its statement read
- **THEN** the statement is produced from the projection read model, listing the entries
  in global-position order

#### Scenario: Concurrent reads do not double-apply

- **WHEN** two reads catch the projection up concurrently against a store whose reads yield
- **THEN** each event is applied exactly once and the balance is not double-counted
