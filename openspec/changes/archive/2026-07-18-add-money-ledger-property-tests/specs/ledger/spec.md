## MODIFIED Requirements

### Requirement: Entries must balance per currency

The ledger SHALL reject a journal entry whose debit and credit totals are not equal for
some currency, recording no event. This holds for any set of legs: a set whose
per-currency debit and credit totals are equal SHALL be accepted, and any set with a
per-currency imbalance SHALL be rejected.

#### Scenario: Unbalanced entry is rejected

- **WHEN** an entry debits `100 USD` on A and credits `90 USD` on B
- **THEN** the posting fails with an unbalanced error and no event is recorded

#### Scenario: Any balanced leg set is accepted and any imbalance rejected

- **WHEN** an arbitrary set of legs whose per-currency debit and credit totals are equal is posted
- **THEN** the entry is accepted
- **AND** perturbing any single leg amount so the totals no longer match causes the posting to be rejected with no event recorded
