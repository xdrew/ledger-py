## ADDED Requirements

### Requirement: A global event feed is exposed

The API SHALL expose a global event feed returning events across all streams in
ascending global-position order from a given position cursor, so the showcase can
stream the append-only log as it grows. The feed SHALL require the API key.

#### Scenario: The feed returns later events in order

- **WHEN** the global event feed is read from a position cursor
- **THEN** it returns events with a greater global position, in ascending order, each with
  its global position, stream type, event type, and time

### Requirement: The playground streams the live event log

The showcase SHALL display the global event log as a live, ordered stream that grows
as new events are appended, showing each event's global position and type, with the
newest events surfaced as they arrive.

#### Scenario: The log grows as the system is driven

- **WHEN** accounts are opened and a transfer is run
- **THEN** the event log view shows the resulting events appearing in global-position order

### Requirement: The saga stage links steps to emitted events

The showcase SHALL present the running transfer as a stage that marks the current
lifecycle step and visually associates it with the events it produces in the log, so
the causal link between a saga step and the events it emits is legible.

#### Scenario: The current step is highlighted while running

- **WHEN** a transfer is progressing through its lifecycle
- **THEN** the current step is highlighted and the events it emits are surfaced in the log view

### Requirement: Accounts show available versus held balances

The showcase SHALL show account balances split into available and held (reserved)
amounts, updating as a transfer moves money, so the hold/settle mechanics are visible.

#### Scenario: A hold shifts available into held

- **WHEN** a transfer places a hold on the source account
- **THEN** the source's available amount decreases and its held amount increases by the same amount in the view
