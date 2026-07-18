## ADDED Requirements

### Requirement: Freeze and close are available through the API

The API SHALL expose operations to freeze and to close an account. Freezing an
open account SHALL transition it to frozen; closing an empty account SHALL
transition it to closed. An invalid transition (freezing a non-open account) SHALL
be rejected with `409`, and closing a non-empty account SHALL be rejected with
`409`.

#### Scenario: Freeze an open account via the API

- **WHEN** an open account is frozen through the API
- **THEN** the account becomes frozen

#### Scenario: Freezing a frozen account is rejected

- **WHEN** a freeze is requested for an account that is not open
- **THEN** the request is rejected with `409`

#### Scenario: Close an empty account via the API

- **WHEN** an empty account is closed through the API
- **THEN** the account becomes closed

#### Scenario: Closing a non-empty account is rejected

- **WHEN** a close is requested for an account holding a non-zero balance
- **THEN** the request is rejected with `409`
