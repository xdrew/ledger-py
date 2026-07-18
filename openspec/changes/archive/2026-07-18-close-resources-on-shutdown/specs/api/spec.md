## ADDED Requirements

### Requirement: Resources are released on shutdown

The application SHALL release the infrastructure resources it opened during
startup — in particular the event-store connection pool — when it shuts down.
Resources supplied to the application from outside (for example a test-injected
context) SHALL NOT be closed by the application's own shutdown.

#### Scenario: An owned context is closed on shutdown

- **WHEN** the application built its own runtime context at startup and then shuts down
- **THEN** the event-store pool it opened is closed

#### Scenario: An injected context is left open

- **WHEN** a runtime context was injected into the application from outside and the application shuts down
- **THEN** the application does not close that injected context
