## Why

Reconciliation added a `resolve_reconciliation` workflow signal, but it can only
be sent through the Temporal UI/CLI — the HTTP API has no way to resolve a parked
transfer. The showcase (and any operator tooling) therefore cannot drive a
`needs_reconciliation` transfer to resolution. Exposing the signal over HTTP makes
the parked-saga lifecycle fully operable from the same surface that starts it.

## What Changes

- Add `POST /api/transfers/{transfer_id}/resolve` accepting a resolution
  (`refund_source` | `retry_credit`); it signals the running workflow.
- Only a transfer currently in `needs_reconciliation` is resolvable; otherwise the
  endpoint returns `409` (via the existing problem-details mapping).
- Extend the `TransferGateway` port with `resolve(...)`; the Temporal
  implementation signals the workflow by its deterministic id.

## Capabilities

### Modified Capabilities

- `transfers`: add a requirement that a parked transfer is resolvable through the
  HTTP API by signalling an operator decision, complementing the existing
  signal-level resolution behavior.

## Impact

- Code: `src/ledger/api/gateway.py` (`resolve` on the port + Temporal impl),
  `src/ledger/api/routers/transfers.py` (endpoint), `src/ledger/api/schemas.py`
  (`ResolveTransferRequest`).
- Tests: `tests/unit/test_api.py` — resolve on a parked transfer signals the
  gateway and returns `202`; resolve on a non-parked transfer returns `409`.
- Enables the saga-cockpit UI (separate `showcase` change) to offer resolve
  controls.
