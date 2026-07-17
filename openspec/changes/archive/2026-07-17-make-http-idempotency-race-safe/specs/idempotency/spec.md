## ADDED Requirements

### Requirement: Idempotency-Key replays the first response

The API SHALL let a mutating request carry an `Idempotency-Key`. The first request
for a key SHALL be processed normally and its response recorded; a later request
with the same key **and the same request** SHALL return the recorded response
without performing the operation again.

#### Scenario: Repeating a request replays the stored response

- **WHEN** a request with an idempotency key succeeds and the identical request is sent again with the same key
- **THEN** the second call returns the same status and body as the first
- **AND** the underlying operation is performed only once

#### Scenario: A request without a key is unaffected

- **WHEN** a request carries no idempotency key
- **THEN** it is processed normally with no de-duplication

### Requirement: Concurrent duplicate requests do not double-apply

The API SHALL claim an idempotency key atomically before performing any
side-effecting work, so that two concurrent requests bearing the same key start
the underlying operation at most once. A concurrent request that finds the key
already claimed but not yet complete SHALL be rejected as a duplicate in progress
rather than starting a second operation.

#### Scenario: Two concurrent requests with one key start the operation once

- **WHEN** two requests with the same idempotency key are processed concurrently
- **THEN** the underlying operation is started exactly once
- **AND** at most one request triggers the work; the other is rejected as a duplicate in progress or receives the first request's recorded response

### Requirement: A reused key with a different request is rejected

The API SHALL bind an idempotency key to a fingerprint of its request. A request
that reuses a key with a different fingerprint SHALL be rejected with a client
error rather than replaying the unrelated stored response.

#### Scenario: Same key, different request

- **WHEN** an idempotency key that was used for one request is reused with a materially different request
- **THEN** the request is rejected with a client error indicating the key was reused with a different request
- **AND** the original stored response is not returned and no new operation is started
