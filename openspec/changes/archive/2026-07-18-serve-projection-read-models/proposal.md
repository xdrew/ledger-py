## Why

The projection runner and the `AccountBalancesProjection` /
`AccountStatementProjection` read models exist and are unit-tested, but nothing
runs them at runtime and no endpoint reads from them — the CQRS read side is dead
code. The API serves balances straight from the write-side aggregate and the
statement straight from the raw event stream, so the projections are decorative.

## What Changes

- Wire the account read models and a `ProjectionRunner` into the application
  context, and serve reads from them: the projection catches up from the global
  log on read (read-your-writes), then serves.
- Add `GET /api/accounts/{id}/balance` served from `AccountBalancesProjection`.
- Serve `GET /api/accounts/{id}/statement` from `AccountStatementProjection`
  instead of re-scanning the raw event stream in the handler.
- The read models are in-memory and rebuilt from the log (checkpoint starts at 0
  each process), so they are self-healing on restart. A durable, cross-instance
  Postgres read model and a continuous background runner are the documented
  production evolution; this change makes the read side genuinely live and
  queryable in-process.

## Capabilities

### Modified Capabilities

- `projections`: add a requirement that the account read models are populated from
  the event log and served through the API, catching up on read.

## Impact

- Code: new `ReadModels` container in `src/ledger/projections/` (balances +
  statement + runner + catch-up); `src/ledger/api/context.py` (build + hold it);
  `src/ledger/api/routers/accounts.py` (balance + statement served from
  projections). Test fixtures gain the read models.
- Tests: the projection-backed balance/statement reflect account activity after
  catch-up.
