## ADDED Requirements

### Requirement: Deposits honor the Idempotency-Key

The API SHALL apply the `Idempotency-Key` mechanism to account deposits: the first
deposit for a key is performed and its response recorded; a later deposit with the
same key and the same request (account, amount, currency) SHALL replay the recorded
response without crediting again; a concurrent duplicate SHALL be rejected as a
duplicate in progress; and the same key reused with a different deposit request
SHALL be rejected.

#### Scenario: Repeated deposit with a key credits once

- **WHEN** a deposit is sent twice with the same idempotency key and the same body
- **THEN** the account is credited only once and the second call returns the first response

#### Scenario: Same key, different deposit is rejected

- **WHEN** an idempotency key used for one deposit is reused with a different amount
- **THEN** the request is rejected with a client error and no second credit occurs
