# deployment Specification

## Purpose
TBD - created by archiving change containerize-app. Update Purpose after archive.
## Requirements
### Requirement: The application is packaged as a container image

The application SHALL be buildable into a container image that installs the project
from the frozen lockfile, runs as a non-root user, and can start each of its
processes (API, worker, migrate, relay) via its console entrypoints.

#### Scenario: The image runs a chosen process

- **WHEN** the image is run with one of the project entrypoints as its command
- **THEN** that process starts using the installed environment

### Requirement: The stack can run the app in containers

The compose stack SHALL be able to run the application's api, worker, and relay as
services against the infrastructure services, gated behind an opt-in profile so the
default `up` brings up infrastructure only.

#### Scenario: Infra-only by default, app on demand

- **WHEN** the stack is brought up without the app profile
- **THEN** only the infrastructure services start
- **AND** bringing it up with the app profile additionally starts the api, worker, and relay

