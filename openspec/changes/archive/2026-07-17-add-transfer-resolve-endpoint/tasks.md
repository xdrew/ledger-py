## 1. Gateway

- [x] 1.1 Add `resolve(transfer_id, decision)` to the `TransferGateway` Protocol.
- [x] 1.2 Implement it on `TemporalTransferGateway`: get the workflow handle by its
  deterministic id (`transfer-{id}`) and send `resolve_reconciliation(decision)`.

## 2. API

- [x] 2.1 Add `ResolveTransferRequest {resolution: ReconciliationResolution}` to
  `schemas.py`.
- [x] 2.2 Add `POST /api/transfers/{transfer_id}/resolve`: load the transfer, 404
  if unknown, `409` (InvalidTransition) if not `needs_reconciliation`, else signal
  via the gateway and return `202`.

## 3. Tests

- [x] 3.1 `test_api.py`: resolve on a parked transfer calls the gateway with the
  decision and returns `202` (fake gateway records the call).
- [x] 3.2 `test_api.py`: resolve on a non-parked transfer returns `409` and does
  not signal.

## 4. Quality gate

- [x] 4.1 `ruff check` + `ruff format --check` + `pyright` (strict) clean.
- [x] 4.2 `uv run pytest` green.
- [x] 4.3 `openspec validate add-transfer-resolve-endpoint --strict` passes.
