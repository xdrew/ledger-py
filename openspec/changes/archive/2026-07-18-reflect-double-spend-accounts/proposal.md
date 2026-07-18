## Why

The double-spend demo creates its own throwaway source/destination, but the Accounts
panel kept showing a *different* account, so after the test the source still read its
old balance (e.g. 100) while the verdict said "debited once, balance 0" — confusing.
Two short account ids could also collide, since the displayed `slice(0,8)` of a
time-ordered UUIDv7 is the timestamp prefix, identical for accounts created in the
same millisecond.

## What Changes

- After the double-spend, the Accounts panel shows the demo's own source and
  destination, so the source visibly ends debited once (100 → 0) and the destination
  holds the one payment that settled (0 → 100) — consistent with the verdict.
- Show a distinct short account id (`0000…tail`) so two accounts are never confused.

## Capabilities

Bug/clarity fix to the existing `showcase` double-spend behavior (which already
requires showing the source's resulting balance). No requirement change; archived
with `--skip-specs`.

## Impact

- Code: `src/ledger/showcase/playground.html` (double-spend updates the accounts
  panel; account-id display). No API/domain changes.
