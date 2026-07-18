## 1. Reversal id + activity

- [x] 1.1 Add `journal_reversal_id_for(transfer_id)` in `operations.py`.
- [x] 1.2 Add a `reverse_journal` activity: load the original entry; if present and
  the reversal not already posted, post a `JournalEntry` with the legs' directions
  swapped (directly, not via the posting service), idempotent; register it.

## 2. Workflow

- [x] 2.1 Track `posted` in `run()` (set after `post_journal` succeeds). On the
  compensation path, if `posted`, execute `reverse_journal` before failing.

## 3. Tests

- [x] 3.1 `test_transfer_saga.py`: a settle_debit failure after posting → transfer
  `Failed`, source restored, and a reversing entry exists whose legs are the swap of
  the original (net zero).

## 4. Quality gate

- [x] 4.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 4.2 `uv run pytest tests/unit tests/integration/test_transfer_saga.py` green.
- [x] 4.3 `openspec validate reverse-journal-on-compensation --strict` passes.
