## ADDED Requirements

### Requirement: The idempotency store is durable and shared

The idempotency store SHALL be available in a durable, shared implementation so
that concurrent requests handled by different workers with the same key start the
underlying operation at most once, and recorded responses survive a restart. The
store SHALL be defined as a contract with interchangeable in-memory (test) and
durable (production) implementations that classify a claim identically as new,
in-progress, mismatched, or a replay.

#### Scenario: Concurrent claims across workers yield one winner

- **WHEN** two requests with the same key and route claim concurrently against the durable store
- **THEN** exactly one claim is classified as new and the other as in-progress or a replay

#### Scenario: A recorded response survives a restart

- **WHEN** a response is recorded for a key and the store is re-opened against the same durable backing
- **THEN** a repeat claim with the same key and fingerprint replays the recorded response

#### Scenario: In-memory and durable stores classify claims identically

- **WHEN** the same sequence of claim/complete calls is applied to the in-memory and durable stores
- **THEN** both classify each claim identically (new, in-progress, mismatch, replay)
