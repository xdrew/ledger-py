## Why

A batch of small production loose ends surfaced in review (#5–#9). Bundled into one
clean-up change (per request) rather than one-per-capability.

## What Changes

- **#6 readyz probes Temporal** — readiness only checked the event store; a transfer
  would fail if Temporal were down while `/readyz` reported ready. Add a Temporal
  health check (`ServiceClient.check_health`) via a `check_health` on the transfer
  gateway; readiness is green only if both the store and Temporal answer.
- **#8 relay resource hygiene** — the `ledger-relay` process opened a second asyncpg
  pool alongside the event store's; reuse the store's pool for the checkpoint and
  publisher. Add graceful shutdown on `SIGTERM` (so `docker stop` drains cleanly),
  not just `SIGINT`.
- **#9 paginate stream reads** — `GET /accounts/{id}/events`, `/accounts/{id}/statement`,
  and `/transfers/{id}/events` returned the whole stream. Add `limit`/`offset` query
  params (bounded) so responses are paginated.
- **#5 shutdown (documented no-op)** — `temporalio.Client` exposes no `close`/`aclose`
  (the connection is process-scoped, released on exit), so there is nothing to close;
  document this in `AppContext.aclose`.
- **#7 `reversal_of` retained (documented)** — it is intentional forward-scaffolding
  for the deferred "reversal of a completed transfer" feature (see `project.md`
  Deferred), not dead code; a comment records that.

## Capabilities

### Modified Capabilities

- `observability`: readiness additionally verifies Temporal connectivity.
- `outbox`: the relay reuses the store's pool and shuts down cleanly on SIGTERM.
- `api`: stream read endpoints are paginated with bounded `limit`/`offset`.

## Impact

- Code: `api/gateway.py` (+`check_health`), `ops/router.py` (readyz), `test_api`
  fakes; `outbox/main.py` (shared pool + signal handlers); `api/routers/accounts.py`
  & `transfers.py` (pagination); `api/context.py` (aclose comment);
  `domain/transfers/events.py` (reversal_of comment).
- Tests: readyz not-ready when Temporal health fails; pagination limits/offsets.
