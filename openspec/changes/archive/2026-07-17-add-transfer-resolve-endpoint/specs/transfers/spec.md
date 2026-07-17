## ADDED Requirements

### Requirement: Parked transfers are resolvable through the HTTP API

The API SHALL expose an operation to resolve a transfer that is in the
`needs_reconciliation` state by supplying an operator decision
(`refund_source` or `retry_credit`), which SHALL be delivered to the running
transfer workflow as its reconciliation signal. The API SHALL reject a resolve
request for a transfer that is not currently in `needs_reconciliation` with a
`409` conflict, and SHALL acknowledge an accepted resolution without waiting for
the workflow to reach its next terminal state.

#### Scenario: Resolving a parked transfer signals the workflow

- **WHEN** a resolve request with a valid decision is made for a transfer in `needs_reconciliation`
- **THEN** the decision is delivered to the transfer workflow as its reconciliation signal
- **AND** the API acknowledges the request as accepted

#### Scenario: Resolving a non-parked transfer is rejected

- **WHEN** a resolve request is made for a transfer that is not in `needs_reconciliation`
- **THEN** the request is rejected with a `409` conflict
- **AND** no reconciliation signal is sent
