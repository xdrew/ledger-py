## Why

The double-spend created a fresh, freshly-funded source on every run, so it always
showed "one settled" — even on a second run when the on-screen source read 0.
That is confusing: after draining the source, a repeat should reject *both*
payments (no funds), not silently mint a new funded account.

## What Changes

- The double-spend uses **one persistent source/destination** across runs. The first
  run arms a fresh source for one payment (one settles, source drains to 0); a repeat
  run on the now-empty source rejects **both** payments for insufficient funds. A
  **Fund source** control re-arms it for another one-wins race.
- The verdict adapts: "exactly one settled" when armed, "both rejected — the source
  is empty" when drained.

## Capabilities

### Modified Capabilities

- `showcase`: the double-spend demo operates on a persistent source, so a repeat on a
  drained source rejects both, and funding re-arms it.

## Impact

- Code: `src/ledger/showcase/playground.html` (persistent demo accounts, Fund source
  control, adaptive verdict). No API/domain changes. Verified live.
