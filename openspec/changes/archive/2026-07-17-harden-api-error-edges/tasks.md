## 1. Implementation

- [x] 1.1 In `problem_details.py`, register a handler for `ConcurrencyConflict`
  mapping it to `409` `application/problem+json` with `code:
  concurrency_conflict`; keep the existing `DomainError` handler.
- [x] 1.2 In `auth.py`, compare the API key with `hmac.compare_digest`, handling a
  `None`/missing header safely (reject with `401`, no length short-circuit).

## 2. Tests

- [x] 2.1 `test_api.py`: a direct write that loses an optimistic-concurrency race
  returns `409` with a problem-details body (`code` `concurrency_conflict`).
- [x] 2.2 `test_api.py`: wrong key → `401`, missing key → `401`, correct key →
  authorized.

## 3. Quality gate

- [x] 3.1 `ruff check` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest` green.
- [x] 3.3 `openspec validate harden-api-error-edges --strict` passes.
