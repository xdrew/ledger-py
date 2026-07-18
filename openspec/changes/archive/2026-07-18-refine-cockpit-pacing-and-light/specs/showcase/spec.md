## MODIFIED Requirements

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
