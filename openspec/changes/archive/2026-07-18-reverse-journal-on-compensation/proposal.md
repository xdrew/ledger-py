## Why

The saga posts the double-entry journal entry (`post_journal`) *before* it settles
the balances. If a step after posting fails and the transfer is compensated —
concretely, `settle_debit` fails because the source was frozen between the hold and
the debit — the compensation releases the hold and fails the transfer, but the
**journal entry stays posted**. The ledger then holds a debit/credit for money that
never moved: a FAILED transfer with a phantom entry, so the trial balance no longer
nets to zero. A double-entry ledger corrects this the accounting-correct way — not
by deleting the write-once entry, but by posting a **reversing entry** that nets it
out.

## What Changes

- Add a deterministic reversal entry id and a `reverse_journal` activity that posts
  a reversing journal entry (debit/credit legs swapped) for a transfer's original
  entry — directly (not through the account-status-checking posting service, since a
  reversal must post even if an account is now frozen), idempotent under retry.
- The workflow, on the compensation path, posts the reversal when the journal had
  already been posted, so a compensated transfer's journal nets to zero.

## Capabilities

### Modified Capabilities

- `transfers`: compensating a transfer after the journal was posted also reverses
  the journal entry, keeping the ledger's trial balance zero-sum for failed transfers.

## Impact

- Code: `src/ledger/domain/transfers/operations.py` (reversal id),
  `src/ledger/temporal/activities/transfer_activities.py` (`reverse_journal`),
  `src/ledger/temporal/workflows/transfer_workflow.py` (post reversal on
  compensation when posted). No domain change — a swapped-legs entry is still a
  balanced `JournalEntry`.
- Tests: `test_transfer_saga.py` — a debit failure after posting leaves the source
  whole, the transfer `Failed`, and a reversing journal entry that nets the original.
