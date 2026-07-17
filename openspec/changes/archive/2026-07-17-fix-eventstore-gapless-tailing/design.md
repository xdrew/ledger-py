## Context

The event store is the system of record. Two downstream tailers — the projection
runner and the outbox relay — consume the *global* stream by repeatedly reading
`read_all(from_position=cursor)` and advancing `cursor` to the last
`global_position` in the batch. Correctness of that pattern rests on one
assumption: **once a consumer has passed position P, no event with position ≤ P
will ever newly appear.** Postgres `GENERATED ALWAYS AS IDENTITY` breaks that
assumption under concurrency.

### The failure

```
T1: INSERT ... (nextval → global_position = 10)         -- not yet committed
T2: INSERT ... (nextval → global_position = 11) ; COMMIT -- visible now
relay: read_all(cursor=9) → [pos 11] ; cursor := 11      -- 10 still invisible
T1: COMMIT                                                -- pos 10 now visible
relay: read_all(cursor=11) → []                          -- pos 10 never read
```

Sequence values are handed out at `INSERT` time and are independent of commit
order, so a lower position can materialize after a higher one has been consumed.
The result is a permanently skipped event for every projector and external
consumer.

## Goals / Non-Goals

**Goals**
- A cursor tail observes every committed event exactly once, regardless of writer
  concurrency (gap-safe consumption).
- No change required in the consumers or the store contract's read surface.
- In-memory and Postgres stores stay behaviorally identical.

**Non-Goals**
- Maximizing append throughput. This log is the money system-of-record; a global
  serialization point is an acceptable, explicitly-chosen cost.
- Eliminating *holes* in the position sequence (rolled-back appends legitimately
  burn a number). Holes are safe; only *reordering* is the defect.

## Decision

Hold a **transaction-scoped global advisory lock** for the entire duration of an
append transaction:

```sql
SELECT pg_advisory_xact_lock($LOCK_KEY);   -- first statement in the txn
-- ... version check, INSERT ... RETURNING global_position ...
-- lock released automatically at COMMIT/ROLLBACK
```

Because the lock is held from before position assignment until commit, appends
serialize: transaction T(n+1) cannot acquire the lock — and therefore cannot draw
its `global_position` — until T(n) has committed and released it. Position
assignment order thus equals commit order, so:

> A committed event's `global_position` is strictly greater than every
> already-committed event's position. A consumer reading committed rows in
> position order can never see a lower position appear after a higher one.

Consumers are then correct as written. `$LOCK_KEY` is a fixed application-chosen
`bigint` constant (namespaced, so it cannot collide with locks taken elsewhere).

### Why not fix the reader instead

The textbook scale-oriented alternative keeps writes concurrent and makes the
*reader* skip in-flight work using a visibility horizon — e.g. store
`pg_current_xact_id()` per row and only consume rows whose xid is below
`pg_snapshot_xmin(pg_current_snapshot())`, treating the largest gap-free
committed position as a moving high-water mark. It preserves append parallelism
but adds a schema column, a non-trivial horizon computation, and edge cases
(long-running transactions stall the horizon; assigning a real xid on every write
has its own costs). For this project the write path is not throughput-bound and
the money-correctness mandate favors the simplest provably-correct design.
Advisory-lock serialization is a handful of lines, easy to reason about, and easy
to test. The horizon approach is documented here as the deliberate next step if
append throughput ever becomes the constraint.

### Interaction with optimistic concurrency

Serializing appends does not weaken the per-stream `UNIQUE(stream_type,
stream_id, version)` guard; it strengthens the surrounding ordering. The
`expected_version` check and its `ConcurrencyConflict` behavior are unchanged —
two writers racing the same stream still resolve to exactly one winner.

## Testing strategy

- **Concurrency regression (Postgres/testcontainers):** launch many overlapping
  appends across several streams with `asyncio.gather`, then fully `drain` a
  tailing consumer and assert (a) it observed exactly the appended count, (b) the
  positions it consumed are strictly increasing, and (c) no event id is missing.
  This exercises the real race the advisory lock closes.
- **Ordering invariant:** after concurrent appends, `read_all` returns positions
  in strictly ascending order with every committed event present.
- Existing single-writer store tests continue to pass unchanged.

## Risks / Tradeoffs

- **Throughput:** all appends serialize on one lock. Accepted and documented; the
  ledger's write volume is bounded by saga steps, not a firehose.
- **Lock key hygiene:** the constant key is namespaced and documented so no other
  code path reuses it.
