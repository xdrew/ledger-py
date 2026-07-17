## Why

Two edge defects in the HTTP surface. First, `ConcurrencyConflict` is not a
`DomainError`, so the problem-details handler never catches it — a lost optimistic
lock on a direct write (e.g. two concurrent deposits to one account) surfaces as a
raw `500` instead of a retryable `409`. The cross-cutting requirement in
`project.md` explicitly says conflicts should be "`409`-class at the edge"; today
they are not. Second, API-key authentication compares with `!=`, which is not
constant-time and leaks a timing side channel on the secret.

## What Changes

- Map `ConcurrencyConflict` to an RFC 7807 `409` problem-details response
  (`code: concurrency_conflict`), consistent with the domain-error handler.
- Compare the API key in constant time (`hmac.compare_digest`), rejecting a
  missing key without short-circuiting on length.
- Establish an `api` capability spec covering problem-details mapping, the
  conflict-to-409 rule, and constant-time auth.

## Capabilities

### New Capabilities

- `api`: the HTTP surface's cross-cutting behavior — RFC 7807 problem details for
  domain and concurrency errors, and constant-time API-key authentication.

## Impact

- Code: `src/ledger/api/problem_details.py` (new handler + status mapping),
  `src/ledger/api/auth.py` (constant-time compare).
- Tests: `tests/unit/test_api.py` — a conflicting concurrent write returns `409`
  with a problem-details body; auth rejects a wrong/missing key.
- No change to request/response schemas or routes.
