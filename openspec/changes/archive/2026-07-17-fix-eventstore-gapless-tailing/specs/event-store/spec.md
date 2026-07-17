## MODIFIED Requirements

### Requirement: Global ordering across streams

The store SHALL assign every persisted event a store-wide monotonically
increasing global position, and SHALL support reading events in global position
order starting after a given position cursor. This drives projections and the
outbox relay.

The store SHALL further guarantee **commit-ordered, gap-safe consumption**: a
committed event's global position SHALL be strictly greater than the global
position of every event that committed before it, so that a consumer tailing the
log in global-position order (advancing a cursor to the highest position it has
seen) can never skip a committed event — even under concurrent appends. Positions
MAY contain holes left by rolled-back appends; such holes SHALL NOT cause a
consumer to miss any committed event.

#### Scenario: Events across different streams receive increasing global positions

- **WHEN** events are appended to two different streams
- **THEN** each persisted event has a global position greater than every event appended
  before it

#### Scenario: Reading from a cursor returns only later events in order

- **WHEN** the global stream is read starting after a given position
- **THEN** only events with a greater global position are returned, in ascending global
  position order

#### Scenario: Concurrent appends are consumed without gaps

- **WHEN** many appends across several streams are committed concurrently and a consumer
  then tails the whole log from position 0 by advancing a cursor to the highest position
  it has seen
- **THEN** the consumer observes every committed event exactly once, in strictly
  increasing global-position order, with no committed event skipped
