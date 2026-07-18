## ADDED Requirements

### Requirement: The cockpit demonstrates concurrent double-spend protection

The showcase SHALL provide a control that funds a source for exactly one payment and
fires two concurrent transfers of that amount, then shows both transfers' outcomes
side by side — exactly one settling and the other being rejected for insufficient
funds — together with the source's resulting balance, so the exactly-once guarantee
under concurrency is visible.

#### Scenario: Two concurrent payments, one settles and one is rejected

- **WHEN** the double-spend control runs two concurrent transfers from a source funded for one
- **THEN** one transfer is shown as completed and the other as rejected for insufficient funds
- **AND** the source is shown debited exactly once
