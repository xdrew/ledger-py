## MODIFIED Requirements

### Requirement: The relay runs continuously and shuts down cleanly

The system SHALL provide a relay loop that repeatedly drains the relay and waits,
publishing new events as they arrive, and that stops cleanly when cancelled,
including when the process receives a termination signal (`SIGINT` or `SIGTERM`) so
an orchestrated stop (for example `docker stop`) drains without error.

#### Scenario: New events are published by the running loop

- **WHEN** the relay loop is running and new events are appended
- **THEN** those events are published without a restart

#### Scenario: The loop stops cleanly on cancellation

- **WHEN** the relay loop is cancelled
- **THEN** it stops without error

#### Scenario: A termination signal stops the relay cleanly

- **WHEN** the relay process receives `SIGTERM`
- **THEN** the loop is cancelled and the process shuts down without error
