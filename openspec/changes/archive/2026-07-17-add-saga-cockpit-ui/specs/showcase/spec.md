## ADDED Requirements

### Requirement: Self-contained playground page

The showcase SHALL serve a single self-contained HTML page (no external asset
requests) that drives the live API to open accounts, deposit, and start a
transfer, using the configured API key.

#### Scenario: The page is served at the root

- **WHEN** the application root is requested
- **THEN** an HTML page titled for the ledger playground is returned
- **AND** it references no external scripts, styles, fonts, or images

### Requirement: Transfer lifecycle is visualized as a stepper

The showcase SHALL render a running transfer's lifecycle as an ordered stepper of
its states (`Initiated`, `Held`, `Posted`, `Completed`), visually distinguishing
completed, current, and pending steps, and SHALL surface the branch outcomes
`Failed` and `NeedsReconciliation`/`Reconciled` distinctly from a normal
completion. The displayed state SHALL track the transfer as polling updates it.

#### Scenario: A completing transfer advances through the stepper

- **WHEN** a started transfer progresses to `Completed`
- **THEN** the stepper shows the lifecycle states up to and including `Completed` as reached
- **AND** a completed transfer is visually distinguished from a failed or parked one

#### Scenario: A parked transfer is shown distinctly

- **WHEN** a transfer is in `needs_reconciliation`
- **THEN** the page presents that state as a parked/attention outcome rather than a normal completion

### Requirement: Transfer event timeline is shown

The showcase SHALL display the transfer's event stream, obtained from the
transfer events endpoint, listing each event's type and ordering information
(version and global position) in order.

#### Scenario: Events are listed in order

- **WHEN** a transfer has emitted several milestone events
- **THEN** the page lists those events in order with their type and position

### Requirement: Parked transfers can be resolved from the page

The showcase SHALL, when a transfer is in `needs_reconciliation`, present controls
to resolve it by refunding the source or retrying the credit, each of which calls
the resolve endpoint with the corresponding decision; after resolving, the page
SHALL continue polling to reflect the resulting state.

#### Scenario: Resolving a parked transfer from the page

- **WHEN** a transfer is parked and the operator chooses a resolution control
- **THEN** the page calls the resolve endpoint with that decision
- **AND** continues polling so the resulting `Reconciled` or `Completed` state becomes visible

#### Scenario: Resolve controls appear only when parked

- **WHEN** a transfer is not in `needs_reconciliation`
- **THEN** the resolve controls are not offered
