# event-store Specification

## Purpose

The append-only event log that is the system of record for money. It persists
domain events into per-aggregate streams with optimistic concurrency, assigns a
store-wide global order, and (de)serializes typed events with schema upcasting. It
backs the `accounts`, `ledger`, and `transfers` write sides and feeds `projections`
and `outbox`.
## Requirements
### Requirement: Append-only event persistence

The event store SHALL persist domain events into a named stream (identified by a
stream type and stream id) and SHALL expose no operation that updates or deletes an
already-persisted event. Once appended, an event is immutable.

#### Scenario: Events appended to a new stream are retrievable

- **WHEN** two events are appended to a previously empty stream
- **THEN** loading that stream returns exactly those two events, in the order appended

#### Scenario: No mutation surface exists

- **WHEN** the event store contract is inspected
- **THEN** it provides only append and read operations and exposes no update or delete
  operation for persisted events

### Requirement: Per-stream sequential versioning

Each event in a stream SHALL be assigned a contiguous, monotonically increasing
version. A new stream starts at version 0; the first appended event is version 1,
and each subsequent event increments the version by exactly one.

#### Scenario: Versions are assigned contiguously

- **WHEN** three events are appended to a new stream
- **THEN** the persisted events carry versions 1, 2, and 3 respectively

### Requirement: Optimistic concurrency control

An append SHALL declare the expected current version of the stream. If the expected
version does not equal the stream's actual current version, the store SHALL reject
the append with a concurrency conflict and SHALL persist none of the events in that
append (the append is atomic). The guard is enforced by a `UNIQUE(stream_type,
stream_id, version)` constraint.

#### Scenario: Append with the matching expected version succeeds

- **WHEN** a stream is at version 2 and an append declares expected version 2
- **THEN** the events are persisted and the stream advances to the new version

#### Scenario: Append with a stale expected version is rejected atomically

- **WHEN** a stream is at version 2 and an append declares expected version 1
- **THEN** the append fails with a concurrency conflict
- **AND** no events from that append are persisted and the stream remains at version 2

#### Scenario: Two concurrent appends from the same expected version — exactly one wins

- **WHEN** two appends to the same stream both declare the same expected version
- **THEN** exactly one append is persisted and the other is rejected with a concurrency
  conflict

#### Scenario: Appending to a new stream expects version 0

- **WHEN** an append to a non-existent stream declares expected version 0
- **THEN** the append succeeds and the stream is created

### Requirement: Stream loading and rehydration

The store SHALL load all events for a given stream in ascending version order, so an
aggregate can be reconstituted from its history.

#### Scenario: Loading an existing stream returns events in version order

- **WHEN** a stream with three events is loaded
- **THEN** the three events are returned ordered by ascending version

#### Scenario: Loading a non-existent stream yields no events

- **WHEN** a stream that was never written is loaded
- **THEN** an empty result is returned and no error is raised

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

### Requirement: Event serialization and metadata

The store SHALL serialize each event to a persistable form recording a stable event
type identifier, an integer schema version, the JSON payload, a unique event id, an
occurred-at timestamp assigned by the store, and correlation / causation / trace
metadata; and SHALL deserialize persisted events back into typed domain events.

#### Scenario: Serialize/deserialize round-trip preserves the event

- **WHEN** an event is appended and then loaded back
- **THEN** the deserialized event equals the original in type and payload

#### Scenario: Event metadata is captured on append

- **WHEN** an event is appended with a correlation id and a causation id
- **THEN** the persisted event records its event id, schema version, occurred-at
  timestamp, and the correlation and causation ids

#### Scenario: Unknown event type cannot be deserialized silently

- **WHEN** a persisted event references a type not present in the type registry
- **THEN** deserialization fails with an explicit error rather than returning a partial
  or untyped event

### Requirement: Trace context round-trips

Event metadata SHALL carry an optional W3C `traceparent` alongside correlation and
causation ids, persisted and rehydrated with the event, so asynchronous consumers
(the outbox relay and projectors) can continue the trace of the request that produced
the event. It SHALL be optional and backward compatible.

#### Scenario: Trace context round-trips through the store

- **WHEN** an event is appended with a `traceparent` in its metadata and later loaded
- **THEN** the loaded event's metadata carries the same `traceparent`

#### Scenario: Events without trace context still load

- **WHEN** an event was stored without a `traceparent`
- **THEN** it loads successfully with a null `traceparent`

### Requirement: Events are upcast on read

Deserialization SHALL transform payloads stored at an older schema version to the
event type's current version by applying registered single-step upcasters in version
order, without ever rewriting stored payloads. Payloads already at the current version
SHALL bypass upcasting. When a stored version is older than the current version and no
upcaster covers a required step, deserialization SHALL fail loudly.

#### Scenario: An old event loads in the current shape

- **WHEN** an event stored at schema version 1 is loaded after its type advanced to
  version 2 with a registered v1→v2 upcaster
- **THEN** the deserialized event has the current shape, with upcaster-supplied values
  for the added fields, and the stored row is unchanged

#### Scenario: Upcasters chain across multiple versions

- **WHEN** an event stored at version 1 is loaded after its type advanced to version 3
  with v1→v2 and v2→v3 upcasters registered
- **THEN** both steps apply in order and the event materializes at version 3's shape

#### Scenario: A missing upcasting step fails loudly

- **WHEN** an event stored at an older version is loaded and no upcaster is registered
  for a required step
- **THEN** deserialization raises a missing-upcaster error instead of building the event
  from the stale payload

### Requirement: Interchangeable in-memory and Postgres implementations

The store SHALL be defined as a structural contract with two interchangeable
implementations — an in-memory double for tests and fast domain iteration, and a
Postgres (asyncpg) implementation for production — that behave identically for
append, load, optimistic-concurrency rejection, and global ordering.

#### Scenario: In-memory store enforces optimistic concurrency identically

- **WHEN** an append with a stale expected version is made against the in-memory store
- **THEN** it is rejected with a concurrency conflict and no events are persisted,
  matching the Postgres store's behavior

#### Scenario: Postgres store preserves global ordering

- **WHEN** events are appended across multiple streams to the Postgres store
- **THEN** reading in global order returns them with monotonically increasing positions

### Requirement: Base aggregate root

A generic base aggregate root SHALL let an aggregate record new events, apply events
to mutate its in-memory state, track its current version, expose and clear its
uncommitted events for persistence, and reconstitute its state by replaying a
historical event stream without re-recording those events.

#### Scenario: Recording an event stages it and mutates state

- **WHEN** an aggregate records a new event
- **THEN** the event appears in its uncommitted events and the aggregate's state
  reflects that event

#### Scenario: Pulling uncommitted events returns and clears them

- **WHEN** uncommitted events are pulled from an aggregate
- **THEN** the staged events are returned and the aggregate's uncommitted list becomes
  empty

#### Scenario: Reconstituting from history rebuilds state without re-recording

- **WHEN** an aggregate is reconstituted from a historical event stream
- **THEN** its state reflects all replayed events, its version equals the last event's
  version, and its uncommitted events list is empty

