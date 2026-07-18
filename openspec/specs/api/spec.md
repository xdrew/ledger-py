# api Specification

## Purpose
TBD - created by archiving change harden-api-error-edges. Update Purpose after archive.
## Requirements
### Requirement: Domain errors map to RFC 7807 problem details

The API SHALL translate every domain error into an `application/problem+json`
response carrying `type`, `title`, `status`, `detail`, and the stable domain
`code`, with the HTTP status derived from the error code (validation errors →
`422`, illegal-state errors → `409`, not-found → `404`, otherwise `400`). It
SHALL NOT leak stack traces or internal messages beyond the domain `detail`.

#### Scenario: A domain rule violation returns a problem-details body

- **WHEN** a request triggers a domain error such as insufficient funds
- **THEN** the response has the mapped HTTP status and an `application/problem+json`
  body with `type`, `title`, `status`, `detail`, and `code`

### Requirement: Concurrency conflicts surface as 409

The API SHALL translate an optimistic-concurrency conflict raised on a direct
write into a `409` `application/problem+json` response with `code:
concurrency_conflict`, rather than an unhandled `500`.

#### Scenario: A lost optimistic lock returns 409

- **WHEN** a direct account write loses an optimistic-concurrency race and raises a
  concurrency conflict
- **THEN** the response status is `409`
- **AND** the body is `application/problem+json` with `code` `concurrency_conflict`

### Requirement: API-key authentication is constant-time

The API SHALL authenticate mutating requests with an API key supplied in a header
and SHALL compare the presented key against the configured key in constant time,
rejecting a missing or incorrect key with `401` without revealing, through timing,
how much of the key matched.

#### Scenario: A wrong key is rejected

- **WHEN** a request presents an incorrect API key
- **THEN** the request is rejected with `401`

#### Scenario: A missing key is rejected

- **WHEN** a request presents no API key
- **THEN** the request is rejected with `401`

#### Scenario: The correct key is accepted

- **WHEN** a request presents the configured API key
- **THEN** the request is authorized

### Requirement: Resources are released on shutdown

The application SHALL release the infrastructure resources it opened during
startup — in particular the event-store connection pool — when it shuts down.
Resources supplied to the application from outside (for example a test-injected
context) SHALL NOT be closed by the application's own shutdown.

#### Scenario: An owned context is closed on shutdown

- **WHEN** the application built its own runtime context at startup and then shuts down
- **THEN** the event-store pool it opened is closed

#### Scenario: An injected context is left open

- **WHEN** a runtime context was injected into the application from outside and the application shuts down
- **THEN** the application does not close that injected context

### Requirement: Stream read endpoints are paginated

Endpoints that return a stream of events or statement lines SHALL accept bounded
`limit` and `offset` query parameters and return at most `limit` items starting at
`offset`, so a long stream cannot force an unbounded response. `limit` SHALL have a
sane default and maximum.

#### Scenario: A limit bounds the response

- **WHEN** a stream read endpoint is called with a `limit`
- **THEN** at most that many items are returned

#### Scenario: An offset skips earlier items

- **WHEN** a stream read endpoint is called with an `offset`
- **THEN** the returned items start after that many items in the stream

