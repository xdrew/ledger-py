# ADR-0002: Python 3.14 baseline and modern language features

- Status: accepted
- Date: 2026-07-15

## Context

The prior author last worked heavily in Python 3.7. The rewrite is a chance to
adopt the current language and toolchain deliberately, not incidentally.

## Decision

Target **Python 3.14** (pinned via `.python-version`, enforced by
`requires-python = ">=3.14"`). Managed with **uv** (interpreter + lockfile), so
the pinned interpreter is reproducible across machines and CI.

Use these features as the default idiom, not as exceptions:

- **PEP 695 generics** — `class AggregateRoot[E]`, `type StreamId = UUID`.
- **PEP 649 deferred annotations** (default in 3.14) — clean forward references
  in domain models without `from __future__ import annotations`.
- **PEP 750 t-strings** — safe, deferred interpolation for SQL/log templating.
- **`uuid.uuid7()`** from the stdlib — time-ordered ids; drops the `ramsey/uuid`
  equivalent dependency the PHP version needed.
- **`enum.StrEnum`** for statuses / failure reasons.
- **Structural pattern matching** (`match`) for event/command dispatch.
- **`asyncio.TaskGroup` + `ExceptionGroup`/`except*`** for concurrent sagas
  (the double-spend race) and parallel pre-checks.
- **`typing.Protocol`, `Self`, `@override`, `assert_never`, `TypeIs`** for a
  structurally-typed domain without deep inheritance.
- **`@dataclass(slots=True, frozen=True)`** for immutable events / value objects.

Verified on 3.14.6 during scaffolding: `temporalio`, `pydantic`, `asyncpg`,
`fastapi` all resolve and import; t-strings and deferred annotations behave.

## Consequences

- Free-threading (officially supported in 3.14) is available for CPU-bound
  projection/outbox workers if contention ever justifies it; the default build
  stays GIL-enabled for wheel compatibility.
- `pyright` runs in `strict` mode against `pythonVersion = "3.14"`.
