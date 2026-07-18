# outbox Specification

## Purpose
TBD - created by archiving change run-outbox-relay-process. Update Purpose after archive.
## Requirements
### Requirement: The relay republishes the event log in global order

The outbox relay SHALL read the global event log in ascending global-position order
from its checkpoint and hand each event to a publisher, advancing the checkpoint
only after an event is published. Delivery is at-least-once: publishers must dedupe
downstream.

#### Scenario: All events are published in order

- **WHEN** several events across streams exist and the relay drains
- **THEN** every event is published in ascending global-position order
- **AND** the checkpoint ends at the latest global position

#### Scenario: A caught-up relay republishes nothing

- **WHEN** the relay has published all events and drains again with no new events
- **THEN** no events are published and the checkpoint is unchanged

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

### Requirement: The relay checkpoint is durable

The relay SHALL persist its checkpoint durably so that, after a restart, it resumes
after the last published position rather than republishing the whole log.

#### Scenario: The checkpoint survives a restart

- **WHEN** the relay publishes up to a position, then a fresh relay is started against the same durable checkpoint
- **THEN** the fresh relay resumes after that position and does not republish earlier events

