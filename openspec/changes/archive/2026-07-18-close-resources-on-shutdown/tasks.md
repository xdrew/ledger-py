## 1. Implementation

- [x] 1.1 Add `AppContext.aclose()` that closes the store if it exposes `aclose`
  (Postgres pool); in-memory store is a no-op.
- [x] 1.2 In `lifespan`, track ownership (context was None at entry), and in a
  `finally` close the context only if the lifespan created it.

## 2. Tests

- [x] 2.1 `test_api.py`: a lifespan that builds its own context closes the store on
  shutdown (spy/fake store records `aclose`); an injected context is not closed.

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit` green.
- [x] 3.3 `openspec validate close-resources-on-shutdown --strict` passes.
