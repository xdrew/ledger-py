# observability Specification

## Purpose
TBD - created by archiving change propagate-correlation-and-trace. Update Purpose after archive.
## Requirements
### Requirement: Correlation id is recorded on a request's events

The system SHALL tag the events produced while handling a request with a
correlation id that ties together the events of one business operation across
streams. For a transfer, the correlation id SHALL be the transfer id, so the
account, journal, and transfer events of that transfer share one correlation id.

#### Scenario: A transfer's events share the transfer id as correlation id

- **WHEN** a transfer runs to a terminal state
- **THEN** the account events, the journal entry event, and the transfer milestone events
  it produced all carry the transfer id as their correlation id

### Requirement: W3C trace context is propagated into event metadata

The system SHALL carry a W3C `traceparent` supplied on the incoming request
through to the events that request produces, recording it in event metadata so
asynchronous consumers can continue the trace. When no `traceparent` is supplied,
events SHALL still be produced with a null `traceparent`.

#### Scenario: A supplied traceparent reaches the events

- **WHEN** a request carrying a `traceparent` header produces events
- **THEN** those events' metadata carry that same `traceparent`

#### Scenario: Absent trace context still produces events

- **WHEN** a request without a `traceparent` header produces events
- **THEN** the events are produced with a null `traceparent` and no error

### Requirement: Readiness reflects critical dependencies

The readiness probe SHALL report ready only when the critical runtime dependencies
are reachable — the event store and Temporal. If either is unreachable, readiness
SHALL report not-ready with a `503`, so traffic is not routed to an instance that
cannot serve transfers.

#### Scenario: Ready when dependencies answer

- **WHEN** the event store and Temporal both answer their health checks
- **THEN** the readiness probe reports ready

#### Scenario: Not ready when Temporal is unreachable

- **WHEN** Temporal does not answer its health check
- **THEN** the readiness probe reports not-ready with a `503`

