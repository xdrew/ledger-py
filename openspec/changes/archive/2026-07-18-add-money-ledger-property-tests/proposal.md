## Why

`hypothesis` is a declared dev dependency and the README lists property-based
testing as part of the toolchain, but there are no property tests — a
claim-vs-reality gap. The money and double-entry invariants (the correctness core
of a ledger) are exactly what property testing is best at: they should hold for
*all* inputs, not just the handful in example-based tests.

## What Changes

- Add hypothesis property tests for the `Money` value object: same-currency
  add/subtract round-trip, negate involution, additive identity, total ordering
  consistency, and cross-currency operations raising.
- Add property tests for the double-entry balance rule (`_assert_balanced`): any
  multiset of legs that balances per currency is accepted, and any imbalance is
  rejected.
- No production behavior changes; this strengthens verification of existing
  `accounts`/`ledger` requirements only.

## Capabilities

No requirement changes — this is a test-only change (archived with `--skip-specs`).
It strengthens verification of the existing money and double-entry requirements.

## Impact

- Tests: new `tests/unit/test_property_money.py` and
  `tests/unit/test_property_ledger.py`.
- No source changes.
