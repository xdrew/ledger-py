## Why

The system's headline money-safety guarantee — two concurrent transfers from a
source funded for only one settle exactly once — is proven in tests but invisible
on the page. A reviewer should be able to *trigger a double-spend* and watch the
ledger let exactly one through and reject the other, with the source debited once.

## What Changes

- Add a **double-spend** control to the cockpit: it funds a fresh source for exactly
  one payment, fires two concurrent transfers of that amount, and shows both as
  side-by-side lanes with their outcomes — one `Completed`, one `Failed`
  (`insufficient_funds`) — plus a verdict and the source's final balance (debited
  once). This visualizes the optimistic-concurrency guarantee.

## Capabilities

### Modified Capabilities

- `showcase`: the cockpit can run a concurrent double-spend and show that exactly one
  payment settles while the other is rejected, with the source debited once.

## Impact

- Code: `src/ledger/showcase/playground.html` (a concurrency section + JS).
- Consumes existing endpoints (accounts, transfers). No API/domain changes.
- Verify live against the running stack; the self-contained playground test passes.
