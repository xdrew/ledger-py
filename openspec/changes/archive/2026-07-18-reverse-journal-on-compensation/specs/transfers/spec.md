## MODIFIED Requirements

### Requirement: A failure before the debit is compensated

The system SHALL, when a transfer fails after the hold is placed but before the source
debit (for example the journal posting fails), release the hold and reach the `Failed`
state, restoring the source's available balance so no money is moved. When a journal
entry had already been posted before the compensating failure, the system SHALL also
post a reversing journal entry (the original entry's debit and credit legs swapped) so
the ledger nets to zero for that transfer — the write-once original is never deleted,
it is reversed.

#### Scenario: Posting fails after the hold

- **WHEN** a transfer's journal posting fails after the source hold was placed
- **THEN** the hold on the source is released and the transfer reaches `Failed`
- **AND** the source's available balance is restored and no money is moved

#### Scenario: A debit failure after posting reverses the journal

- **WHEN** the source debit fails after the journal entry was posted, and the transfer is compensated
- **THEN** the hold is released, the source balance is restored, and the transfer reaches `Failed`
- **AND** a reversing journal entry is posted so the original entry and its reversal net to zero
