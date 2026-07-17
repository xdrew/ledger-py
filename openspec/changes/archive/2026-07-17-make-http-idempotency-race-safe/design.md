## Context

The current store exposes `recall`/`remember` — a read then a later write with
the side-effecting `gateway.start` in between. Nothing reserves the key during
that window, and the body is never considered. The fix is to model the key's
lifecycle explicitly and claim it atomically before any work.

## Goals / Non-Goals

**Goals**
- Two concurrent requests with the same key start the operation at most once.
- A completed key replays its response only for a matching request; a mismatched
  reuse is rejected, not mis-replayed.
- The contract is storage-agnostic so a Postgres/TTL backing is a later drop-in.

**Non-Goals**
- Cross-process correctness *today* (the in-memory store is per-process; the
  claim semantics are chosen so the Postgres version is a mechanical port).
- A blocking wait for an in-flight request to finish — a concurrent duplicate is
  rejected fast; the client retries and gets the replay once complete.

## Decision

Model each key/route entry with two states and expose an atomic `claim`:

```python
class ClaimResult(Enum): NEW; IN_PROGRESS; MISMATCH; REPLAY

def claim(key, route, fingerprint) -> tuple[ClaimResult, StoredResponse | None]:
    entry = self._entries.get((key, route))
    if entry is None:
        self._entries[(key, route)] = _Entry(fingerprint, response=None)  # reserve
        return NEW, None
    if entry.fingerprint != fingerprint:
        return MISMATCH, None
    if entry.response is None:
        return IN_PROGRESS, None          # a concurrent request holds the claim
    return REPLAY, entry.response

def complete(key, route, status, body) -> None:
    self._entries[(key, route)].response = StoredResponse(status, body)
```

`claim` performs no `await`, so under FastAPI's single-threaded event loop it is
atomic with respect to other requests: the first caller transitions the entry to
*reserved* before yielding at `await gateway.start(...)`, so a concurrent second
caller observes `IN_PROGRESS`. The route handler maps results:

- **NEW** → do the work, then `complete(...)`, return the response.
- **REPLAY** → return the stored response (same status/body).
- **IN_PROGRESS** → `409` problem-details "duplicate request in progress"
  (client may retry to get the replay).
- **MISMATCH** → `422` problem-details "idempotency key reused with a different
  request".

### Fingerprint

A stable hash of the semantic request: route + sorted request body fields
(source, destination, amount, currency). Computed with `hashlib.sha256` over a
canonical `json.dumps(..., sort_keys=True)`. It excludes the server-minted
`transfer_id` (which does not exist yet at claim time).

### Failure handling

If the work raises after a NEW claim, the reservation is released
(`discard(key, route)`) so the key is not poisoned into a permanent
`IN_PROGRESS`. The client can retry cleanly.

### Why not just lock

A per-key `asyncio.Lock` would serialize duplicates and make the second wait for
the first, then replay. That is heavier (holds a coroutine, needs lock GC) and
gives no better guarantee than fast-reject-then-retry for this surface. The claim
map is simpler and ports directly to `INSERT ... ON CONFLICT DO NOTHING` +
fingerprint column in Postgres.

## Testing strategy

- Concurrent same-key: fire two `create_transfer` calls with one key via
  `asyncio.gather` against a fake gateway that counts `start` calls; assert
  `start` ran once and the second response is a `409` (or the replay), never a
  second saga.
- Replay: same key, same body, sequential → identical stored response, `start`
  once.
- Mismatch: same key, different body → `422`, no second `start`.
- No-key requests are unaffected.

## Risks / Tradeoffs

- In-memory store is per-process; documented, with the Postgres port pre-designed.
- Fast-reject on in-progress duplicates pushes a retry onto the client; acceptable
  and standard for Idempotency-Key semantics.
