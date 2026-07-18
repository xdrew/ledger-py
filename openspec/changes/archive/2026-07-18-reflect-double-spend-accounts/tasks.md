## 1. Fix

- [x] 1.1 After the double-spend, set the tracked accounts to the demo's own and
  render the Accounts panel (source 100 → 0, destination 0 → 100).
- [x] 1.2 Display a distinct short account id (prefix + tail) so two accounts created
  in the same millisecond are not confused.

## 2. Verify

- [x] 2.1 Live: after the double-spend the Accounts panel shows source 0 and
  destination 100 with distinct ids, matching the verdict.
- [x] 2.2 `uv run pytest tests/unit` green (self-contained playground test passes).
