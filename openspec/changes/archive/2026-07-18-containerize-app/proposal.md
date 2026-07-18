## Why

The compose stack runs only infrastructure (Postgres, Temporal, OTel, Grafana);
the app (api, worker, relay) runs on the host via `uv`. There is no container
image, so the service cannot be built and deployed as a unit — the README's
"deploy" story stops at the host. A production-grade portfolio piece should ship a
reproducible image and run its own processes in the stack.

## What Changes

- Add a multi-stage `Dockerfile` (uv-based, frozen lockfile, non-root runtime,
  pinned base) that installs the project and exposes the `ledger-api`,
  `ledger-worker`, `ledger-migrate`, and `ledger-relay` entrypoints.
- Add a `.dockerignore` so the build context stays small and reproducible.
- Add `api`, `worker`, and `relay` services to compose behind an `app` profile so
  `just up` still brings up infra only, and `docker compose --profile app up`
  runs the whole system in containers.

## Capabilities

### New Capabilities

- `deployment`: the application is packaged as a container image and its processes
  run as services in the stack.

## Impact

- Files: new `Dockerfile`, `.dockerignore`; `docker-compose.yml` app services.
- No source changes. Build/run verification requires a working Docker daemon.
