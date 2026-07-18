## ADDED Requirements

### Requirement: A Helm chart deploys the app to Kubernetes

The project SHALL provide a Helm chart that deploys the application to Kubernetes —
the API, the Temporal worker, and the outbox relay as Deployments, and database
migrations as a pre-install/pre-upgrade Job (never on app boot) — parameterized by
image, non-secret config (ConfigMap), and secrets (Secret), with the API exposed by
a Service and health/readiness probes on the API.

#### Scenario: The chart renders and lints

- **WHEN** the chart is linted and templated
- **THEN** it passes lint and renders valid manifests for the api, worker, relay, and
  migration Job

### Requirement: A green main deploys to the server

On a push to `main`, after the tests pass, the pipeline SHALL build the production
image and push it to the container registry, then roll it out to the server's
Kubernetes over an SSH forced-command, and SHALL verify the deployment by checking
the public readiness endpoint.

#### Scenario: Deploy runs only on green main

- **WHEN** the pipeline runs on a push to `main` and the tests pass
- **THEN** the image is pushed to the registry and the deploy step rolls it out and
  verifies the public `/readyz`

#### Scenario: Deploy does not run on pull requests

- **WHEN** the pipeline runs for a pull request
- **THEN** the image is not pushed and the deploy step does not run
