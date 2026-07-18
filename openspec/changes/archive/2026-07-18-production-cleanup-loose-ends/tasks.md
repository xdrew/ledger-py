## 1. #6 readyz probes Temporal

- [x] 1.1 Add `check_health()` to the `TransferGateway` protocol; Temporal impl calls
  `client.service_client.check_health()`. Update test fakes.
- [x] 1.2 `readyz` reports not-ready (`503`) if the store OR Temporal health fails.

## 2. #8 relay resource hygiene

- [x] 2.1 In `outbox/main.py`, reuse the store's pool (`PostgresEventStore.pool`) for
  the checkpoint + publisher instead of a second pool.
- [x] 2.2 Install `SIGTERM`/`SIGINT` handlers that cancel the relay loop for a clean
  shutdown.

## 3. #9 paginate stream reads

- [x] 3.1 Add bounded `limit`/`offset` query params to
  `GET /accounts/{id}/events`, `/accounts/{id}/statement`, `/transfers/{id}/events`.

## 4. #5 / #7 documented decisions

- [x] 4.1 Comment in `AppContext.aclose` that `temporalio.Client` has no close
  (process-scoped connection) — nothing to release.
- [x] 4.2 Comment on `TransferInitiated.reversal_of` that it is intentional
  scaffolding for the deferred reversal feature.

## 5. Tests & gate

- [x] 5.1 `test_api.py`: readyz not-ready when the gateway health check fails;
  pagination `limit`/`offset` on the stream endpoints.
- [x] 5.2 `ruff` + `ruff format --check` + `pyright` + `pytest` green.
- [x] 5.3 `openspec validate production-cleanup-loose-ends --strict` passes.
