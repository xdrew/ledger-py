## MODIFIED Requirements

### Requirement: The cockpit demonstrates concurrent double-spend protection

The showcase SHALL provide a control that fires two concurrent transfers from one
persistent source and shows both transfers' outcomes side by side, together with the
source's resulting balance, so the exactly-once guarantee under concurrency is
visible. When the source is armed for one payment, exactly one transfer SHALL settle
and the other SHALL be rejected for insufficient funds. When the source is empty (for
example after a previous run drained it), both transfers SHALL be rejected for
insufficient funds. A control SHALL let the operator fund the source to arm it for
another race.

#### Scenario: Two concurrent payments, one settles and one is rejected

- **WHEN** the double-spend runs two concurrent transfers from a source armed for one payment
- **THEN** one transfer is shown as completed and the other as rejected for insufficient funds
- **AND** the source is shown debited exactly once

#### Scenario: A repeat on the drained source rejects both

- **WHEN** the double-spend is run again on the same source after it was drained
- **THEN** both transfers are shown as rejected for insufficient funds
- **AND** the verdict indicates the source is empty and can be re-armed by funding it
