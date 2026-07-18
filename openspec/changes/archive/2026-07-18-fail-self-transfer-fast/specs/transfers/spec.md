## MODIFIED Requirements

### Requirement: Initiate a transfer

The system SHALL initiate a transfer between a source and destination account for a
positive amount, recording `TransferInitiated` and placing the transfer in the
`Initiated` state. The source and destination accounts MUST be different; a
transfer whose source equals its destination SHALL be rejected before any event is
recorded. The API SHALL reject a self-transfer at request time with a `422` before
starting the saga, and the initiate activity SHALL treat a self-transfer as a
non-retryable failure (it is not a transient error to retry).

#### Scenario: Initiating a transfer

- **WHEN** a transfer of `100 USD` is initiated from account A to account B
- **THEN** a `TransferInitiated` event is recorded and the transfer is in the `Initiated` state

#### Scenario: A self-transfer is rejected at the API

- **WHEN** a transfer request has the same source and destination account
- **THEN** the API rejects it with `422` and does not start the saga

#### Scenario: A self-transfer that reaches the activity fails fast

- **WHEN** the initiate activity is run for a self-transfer
- **THEN** it fails with a non-retryable error rather than being retried as transient
