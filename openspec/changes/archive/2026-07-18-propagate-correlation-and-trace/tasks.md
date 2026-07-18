## 1. Message boundary

- [x] 1.1 Add `traceparent: str | None = None` to `TransferInput` so it crosses the
  workflow/activity boundary.

## 2. Activities

- [x] 2.1 Add a helper on `TransferActivities` building
  `EventMetadata(correlation_id=data.transfer_id, traceparent=data.traceparent)`.
- [x] 2.2 Pass that metadata to every `save` in the saga activities (transfer
  milestones, account holds/debits/credits/refund, journal posting).

## 3. API

- [x] 3.1 `transfers.py`: read the `traceparent` header on create and set it on
  `TransferInput`.
- [x] 3.2 `accounts.py`: on open/deposit, save with
  `EventMetadata(correlation_id=account_id, traceparent=<request traceparent>)`.

## 4. Tests

- [x] 4.1 Saga/integration or unit: after a transfer, its account, journal, and
  transfer events all carry the transfer id as correlation id, and a supplied
  traceparent is preserved on the events.
- [x] 4.2 `test_api.py`: an account open/deposit records the account id as
  correlation id; a supplied traceparent round-trips; absent traceparent is null.

## 5. Quality gate

- [x] 5.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 5.2 `uv run pytest tests/unit tests/integration/test_transfer_saga.py` green.
- [x] 5.3 `openspec validate propagate-correlation-and-trace --strict` passes.
