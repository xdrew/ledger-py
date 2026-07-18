## Why

Two cockpit issues from live use. First, the saga runs in milliseconds locally, so
the lifecycle stepper jumps straight to the outcome — a viewer never sees the
`Held`/`Posted` stages or the money shift from available to held. Second, the dark
theme is harder to read for this audience; a light theme is preferred.

## What Changes

- **Pace the playback**: reveal the saga milestones from the real event stream one at
  a time (~0.85s each) so `Initiated → Held → Posted → outcome` is watchable, and
  drive the account bars from the revealed milestone so available→held→settled is
  visible. The event log prints new rows as a staggered ticker rather than dumping a
  burst. This is honest — real event order and amounts, paced for viewing.
- **Light theme**: switch the cockpit to a light "daylight financial terminal"
  surface, keeping the brass / ledger-green / oxblood accent identity and the
  monospace-forward log.

## Capabilities

### Modified Capabilities

- `showcase`: the saga stage reveals stages at an observable pace (not instantly),
  and the page uses a light theme.

## Impact

- Code: `src/ledger/showcase/playground.html` (theme + paced playback JS).
- No API/store changes. Self-contained page; the playground test still passes.
- Verify live against the running stack.
