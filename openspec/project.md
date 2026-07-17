# Project: ledger-core (Python + Temporal)

An event-sourced payment ledger — the backend internals of a wallet / neobank-style
service, orchestrated with [Temporal](https://temporal.io/). Accounts hold money;
users deposit and transfer. The entire point is **correctness of money under
concurrency and partial failure**: no lost updates, no double-spend, safe
compensation, honest reconciliation, full auditability. A senior-grade backend
portfolio piece demonstrating DDD, CQRS, Event Sourcing, and **durable-execution
sagas** — no UI beyond a thin playground.

This is a Python 3.14 rewrite of the original PHP/Symfony `ledger-core`,
re-architected around Temporal. The problem shape — long-running, failure-prone
operations across several systems, with partial failures, compensation,
reconciliation, and a hard audit trail — is the same shape as network-service
orchestration (L2/L3 VPN provisioning). Only the domain nouns differ.

## Vision & Scope

**In scope:**
- Account lifecycle (open, deposit, hold/release, debit/credit, freeze, close;
  available vs reserved balance)
- Double-entry ledger (immutable, balanced postings)
- Transfers as a **Temporal workflow saga** (hold → post → settle; compensate on
  pre-debit failure; park for reconciliation on residual credit failure)
- Idempotent money operations (deterministic operation ids) and HTTP-level
  request idempotency (Idempotency-Key)
- Read projections (balances, statement; rebuildable)
- Outbox relay for reliable external event publication
- HTTP API (FastAPI, RFC 7807 problem details)
- Ops wrapping: observability (OpenTelemetry + structlog), health/readiness

**Explicitly out of scope (non-goals):**
- Rich UI / frontend (only a self-contained playground page)
- Real banking rails / card networks; KYC / compliance
- Multi-tenant auth beyond a simple API key
- FX / cross-currency conversion — accounts are single-currency; the ledger
  enforces currency consistency per entry

**Deferred (not yet implemented; tracked as future changes):**
- Reversal of a completed transfer (compensating swapped transfer)
- Natural-language statement query

## Tech Stack & Constraints

- **Python 3.14**, managed with **uv** (pinned interpreter + lockfile). Modern
  language features are the default idiom: PEP 695 generics, PEP 649 deferred
  annotations, PEP 750 t-strings, stdlib `uuid.uuid7()`, `StrEnum`, structural
  pattern matching, `asyncio.TaskGroup` / `except*`.
- **Temporal** (`temporalio`) — workflows + activities; pydantic data converter.
- **FastAPI** + **uvicorn** — HTTP surface, RFC 7807 errors.
- **PostgreSQL** via **asyncpg** (raw SQL, no ORM) — event store, projections,
  outbox support tables.
- **OpenTelemetry** + **structlog** — traces, structured logs.
- Dev toolchain: **ruff** (lint + format), **pyright** (strict), **pytest** +
  **hypothesis** + **testcontainers** + Temporal time-skipping test env, coverage,
  **mutmut** (mutation testing), GitHub Actions CI gate.
- **Money** as integer minor units + ISO-4217 currency. Never floats. Always via a
  `Money` value object. Single-currency accounts.
- All source is fully type-annotated; `pyright` runs in `strict` mode.

## Architecture Principles

- **Two ownership boundaries, kept separate (ADR-0001):**
  - **Temporal owns the process** — the transfer saga (hold → post → settle,
    retries, compensation, timers) lives in a Temporal workflow. Durable
    execution: crashes resume, activities retry per policy, stuck sagas are
    *visible* in the Temporal UI.
  - **The event store owns the state** — Accounts (balances) and the Ledger
    (journal) are event-sourced in Postgres, with `UNIQUE(stream_type, stream_id,
    version)` as the optimistic-concurrency guard. This append-only log is the
    system of record for money.
- **Activities are the only side-effect boundary.** They call the domain, append
  account/journal events, and also append transfer milestone events for the
  audit/read/showcase surfaces — not for durability (Temporal owns that).
- **Hexagonal / ports & adapters.** The domain (`ledger.domain.*`) has no
  framework, Temporal, or DB dependency.
- **Bounded contexts:** `accounts`, `ledger`, `transfers`; a shared kernel holds
  `Money`, identifiers, `DomainEvent`, and `AggregateRoot[E]`.
- **CQRS:** commands mutate via aggregates → events; queries read from projections
  (or, for strong-consistency reads, straight from the aggregate).
- **Deliberate restraint:** projections and the HTTP idempotency store are plain
  mutable tables, not event-sourced. Event Sourcing is used only where audit and
  replay are a real domain requirement.

## Cross-Cutting Requirements

- **Concurrency:** every aggregate write uses expected-version optimistic locking;
  conflicts surface as a retriable conflict (retried inside the saga; `409`-class
  at the edge).
- **Idempotency:** balance-moving operations carry a deterministic `operation_id`
  derived from the transfer id + step, so activity retries and workflow replays are
  safe no-ops. HTTP mutations may carry an `Idempotency-Key`.
- **Partial-failure safety (ADR-0003):** a failure *before* the source debit is
  fully compensated (release hold → `Failed`, no money moved). A failure *after*
  the debit (residual credit failure) is **not** recorded as `Failed` — the
  workflow parks in `needs_reconciliation`, loudly visible, awaiting reconciliation.
- **Event versioning:** events carry a schema version; an upcaster chain migrates
  old event shapes on load (ADR-0002 context).
- **Correlation:** event metadata carries correlation / causation / `traceparent`,
  propagated into logs and traces.
- **Determinism:** the workflow is deterministic (activities only); the domain and
  projectors are side-effect-free and replay-safe.

## Project Conventions

- Work proceeds through OpenSpec: one capability per change = one reviewable PR.
  Never bundle capabilities.
- For every change: `proposal.md`, `design.md` (where a decision is non-trivial),
  `tasks.md`, and a spec delta under `changes/<id>/specs/<capability>/spec.md`.
- `openspec validate <id> --strict` is a hard gate before implementation.
- The quality gate — `ruff check`, `ruff format --check`, `pyright` (strict),
  `pytest` — must be green before archiving. Implement → tests green →
  `openspec archive <id>`.
- Architecture Decision Records live in `docs/adr/`.

## Capability Map

| Capability      | Responsibility                                                              |
|-----------------|----------------------------------------------------------------------------|
| `event-store`   | Append-only event log; optimistic concurrency; serialization + upcasters   |
| `accounts`      | Account lifecycle aggregate; available vs reserved; idempotent moves       |
| `ledger`        | Immutable double-entry journal; balanced postings                          |
| `transfers`     | Transfer saga on Temporal: hold → post → settle / compensate / park        |
| `projections`   | Read models (balances, statement); rebuildable, replay-safe                |
| `idempotency`   | HTTP-level dedup via Idempotency-Key (app-layer)                           |
| `outbox`        | Relay that republishes the event log to external consumers                 |
| `api`           | FastAPI HTTP surface; RFC 7807 problem details; API-key auth               |
| `observability` | OpenTelemetry traces, structlog logs, health / readiness probes            |
