# showcase Specification

## Purpose
TBD - created by archiving change add-saga-cockpit-ui. Update Purpose after archive.
## Requirements
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

### Requirement: A global event feed is exposed

The API SHALL expose a global event feed returning events across all streams in
ascending global-position order from a given position cursor, so the showcase can
stream the append-only log as it grows. The feed SHALL require the API key.

#### Scenario: The feed returns later events in order

- **WHEN** the global event feed is read from a position cursor
- **THEN** it returns events with a greater global position, in ascending order, each with
  its global position, stream type, event type, and time

### Requirement: The playground streams the live event log

The showcase SHALL display the global event log as a live, ordered stream that grows
as new events are appended, showing each event's global position and type, with the
newest events surfaced as they arrive.

#### Scenario: The log grows as the system is driven

- **WHEN** accounts are opened and a transfer is run
- **THEN** the event log view shows the resulting events appearing in global-position order

### Requirement: The saga stage links steps to emitted events

The showcase SHALL present the running transfer as a stage that marks the current
lifecycle step and visually associates it with the events it produces in the log, so
the causal link between a saga step and the events it emits is legible. Because the
saga can complete near-instantly, the stage SHALL reveal the lifecycle stages at an
observable pace — advancing through `Initiated`, `Held`, `Posted`, and the outcome
one at a time from the real event stream — rather than jumping straight to the
outcome.

#### Scenario: The current step is highlighted while running

- **WHEN** a transfer is progressing through its lifecycle
- **THEN** the current step is highlighted and the events it emits are surfaced in the log view

#### Scenario: Stages are revealed at an observable pace

- **WHEN** a transfer completes near-instantly on the backend
- **THEN** the stage still advances through the lifecycle stages one at a time so a viewer can see each stage, ending on the true outcome

### Requirement: Accounts show available versus held balances

The showcase SHALL show account balances split into available and held (reserved)
amounts, updating as a transfer moves money, so the hold/settle mechanics are visible.
The balances SHALL track the revealed saga stage during paced playback, so the shift
from available to held and then to settled is observable.

#### Scenario: A hold shifts available into held

- **WHEN** the paced playback reaches the hold stage of a transfer
- **THEN** the source's available amount decreases and its held amount increases by the same amount in the view

#### Scenario: Settlement moves the money to the destination

- **WHEN** the paced playback reaches a completed outcome
- **THEN** the source's held amount clears and the destination's available amount increases by the transfer amount

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

