# ledger Specification

## Purpose

The immutable double-entry journal. A journal entry is a balanced set of debit/credit
legs, posted once as a `JournalEntryPosted` event. The posting service validates the
referenced accounts (existence, status, currency) before an entry is built. The ledger
is the accounting record complementary to the account balance events.
## Requirements
### Requirement: Post a balanced double-entry journal entry

The ledger SHALL post a journal entry of legs, where each leg debits or credits a
strictly positive amount on an account, and SHALL emit a single `JournalEntryPosted`
event. The entry SHALL be balanced: for every currency in the entry, the sum of debit
amounts equals the sum of credit amounts, and the entry SHALL contain at least one
debit and one credit leg.

#### Scenario: Posting a balanced two-leg entry

- **WHEN** an entry is posted debiting `100 USD` on account A and crediting `100 USD` on account B
- **THEN** a `JournalEntryPosted` event is recorded with both legs
- **AND** the entry is balanced

#### Scenario: Posting a balanced multi-leg entry

- **WHEN** an entry is posted debiting `100 USD` on A and crediting `70 USD` on B and `30 USD` on C
- **THEN** a `JournalEntryPosted` event is recorded with the three legs

### Requirement: An entry must have both a debit and a credit

The ledger SHALL reject a journal entry that has no legs, or that has only debit legs
or only credit legs, recording no event.

#### Scenario: Single-leg entry is rejected

- **WHEN** an entry with only one debit leg is posted
- **THEN** the posting fails with an unbalanced/too-few-legs error and no event is recorded

#### Scenario: Empty entry is rejected

- **WHEN** an entry with no legs is posted
- **THEN** the posting fails with an unbalanced error and no event is recorded

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

### Requirement: Leg amounts must be positive

The ledger SHALL require every leg amount to be strictly positive; a zero or negative
leg amount is rejected with no event recorded.

#### Scenario: Zero-amount leg is rejected

- **WHEN** an entry contains a leg of `0 USD`
- **THEN** the posting fails with an invalid-amount error and no event is recorded

### Requirement: Posting validates referenced accounts

The posting service SHALL, before building an entry, resolve every referenced account
through an account-status reader and reject the posting when an account is unknown, is
not `Open`, or has a currency different from its leg — recording no event.

#### Scenario: Posting that references an unknown account is rejected

- **WHEN** an entry references an account the reader does not know
- **THEN** the posting fails with an unknown-account error and no event is recorded

#### Scenario: Posting that references a frozen account is rejected

- **WHEN** an entry references an account that is `Frozen`
- **THEN** the posting fails with an account-not-active error and no event is recorded

#### Scenario: Posting with a currency mismatch is rejected

- **WHEN** a leg's currency differs from its referenced account's currency
- **THEN** the posting fails with a currency-mismatch error and no event is recorded

### Requirement: Journal entries are immutable

A posted journal entry SHALL never be amended; its event stream contains exactly one
`JournalEntryPosted` event. Corrections are made by posting new compensating entries.

#### Scenario: A posted entry's stream holds a single event

- **WHEN** a journal entry is posted and its stream is loaded
- **THEN** the stream contains exactly one `JournalEntryPosted` event

### Requirement: Journal entries rehydrate from the event store

A journal entry's legs SHALL be reconstructable by replaying its persisted event, with
no difference from the posted entry.

#### Scenario: Rehydrating a posted entry

- **WHEN** an entry is posted, saved, and reloaded from the ledger repository
- **THEN** the reloaded entry has the same legs (account, direction, amount) as posted

### Requirement: The ledger reconciles to a global zero-sum (trial balance)

Across all posted journal entries, for every currency the sum of debit amounts SHALL
equal the sum of credit amounts (a global net of zero), and each account's
debits-minus-credits net SHALL be consistent with those entries.

#### Scenario: N balanced entries net to zero

- **WHEN** any number of individually balanced entries are posted
- **THEN** summing all legs yields, for each currency, total debits equal to total credits
- **AND** each account's debits-minus-credits net is consistent with those entries

