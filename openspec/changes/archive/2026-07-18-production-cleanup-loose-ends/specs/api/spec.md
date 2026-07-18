## ADDED Requirements

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
