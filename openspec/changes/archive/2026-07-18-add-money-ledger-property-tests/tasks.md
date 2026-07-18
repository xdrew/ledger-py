## 1. Money properties

- [x] 1.1 `tests/unit/test_property_money.py`: for same-currency amounts —
  `a.add(b).subtract(b) == a`; `a.negate().negate() == a`; `a.add(zero) == a`;
  ordering agrees with integer amounts; cross-currency add/subtract/compare raise
  `CurrencyMismatch`.

## 2. Double-entry properties

- [x] 2.1 `tests/unit/test_property_ledger.py`: a generated set of legs that
  balances per currency passes `_assert_balanced`; perturbing one leg's amount
  makes it raise `UnbalancedEntry`; all-debit or all-credit sets are rejected.

## 3. Quality gate

- [x] 3.1 `ruff` + `ruff format --check` + `pyright` (strict) clean.
- [x] 3.2 `uv run pytest tests/unit` green (property tests included).
- [x] 3.3 `openspec validate add-money-ledger-property-tests --strict` passes.
