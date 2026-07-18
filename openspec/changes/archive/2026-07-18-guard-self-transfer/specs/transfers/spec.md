## MODIFIED Requirements

### Requirement: Initiate a transfer

The system SHALL initiate a transfer between a source and destination account for a
positive amount, recording `TransferInitiated` and placing the transfer in the
`Initiated` state. The source and destination accounts MUST be different; a
transfer whose source equals its destination SHALL be rejected before any event is
recorded.

#### Scenario: Initiating a transfer

- **WHEN** a transfer of `100 USD` is initiated from account A to account B
- **THEN** a `TransferInitiated` event is recorded and the transfer is in the `Initiated` state

#### Scenario: A self-transfer is rejected

- **WHEN** a transfer is initiated with the same account as source and destination
- **THEN** it is rejected as a same-account transfer and no event is recorded
