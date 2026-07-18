## 1. Light theme

- [x] 1.1 Reskin `playground.html` to a light surface, keeping the brass /
  ledger-green / oxblood accents and the monospace log.

## 2. Paced playback

- [x] 2.1 Reveal saga milestones from the real event stream one per ~0.85s
  (`Initiated → Held → Posted → outcome`), ending on the true status.
- [x] 2.2 Drive account bars from the revealed milestone (available→held→settled),
  reconciling to real balances at the end.
- [x] 2.3 Print new event-log rows as a staggered ticker instead of a burst.

## 3. Verify & gate

- [x] 3.1 Drive live: a transfer visibly advances Held→Posted→Completed with the
  bars shifting; balances end correct.
- [x] 3.2 `uv run pytest tests/unit` green (self-contained test passes).
- [x] 3.3 `openspec validate refine-cockpit-pacing-and-light --strict` passes.
