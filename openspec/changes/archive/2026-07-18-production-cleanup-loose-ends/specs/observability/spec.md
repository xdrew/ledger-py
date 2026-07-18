## ADDED Requirements

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
