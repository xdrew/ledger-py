## Why

The repo builds and tests but has no continuous delivery. The sibling `ledger`
project deploys by building a production image to GHCR, then a `main`-only job
SSHes to the server and runs a forced-command that rolls the image out to
Kubernetes via a Helm chart, verified by a `/readyz` check. This change mirrors
that pipeline for `ledger-py` (Python), so a green `main` deploys automatically.

## What Changes

- Add a **Helm chart** `deploy/helm/ledger-py` (api, worker, relay, a pre-upgrade
  migration Job/hook, service, config/secret, api HPA, PDB, optional ingress),
  mirroring the sibling chart and adapted for Python (`ledger-api/worker/relay/
  migrate` entrypoints, port 8000, `LEDGER_*` env, native SIGTERM).
- Add CI stages to `.github/workflows/ci.yml`:
  - **chart** — `helm lint` + `helm template` validate the chart on every run.
  - **build** — build the image and, on `main`, push it to
    `ghcr.io/<owner>/ledger-py` (tags `latest` + `sha-<long>`).
  - **deploy** — `main` only, after CI + build: SSH to the server and run the
    forced-command `ledger-py-deploy sha-<SHA>` (the server pulls the chart from the
    repo and the image from GHCR and applies it), then verify the public `/readyz`.
- Document the server-side prerequisites and the required GitHub secrets/vars.

## Capabilities

### Modified Capabilities

- `deployment`: a green `main` builds the image to GHCR and rolls it out to
  Kubernetes via the Helm chart over an SSH forced-command, verified by `/readyz`.

## Impact

- Files: new `deploy/helm/ledger-py/**`, `deploy/DEPLOY.md`; `.github/workflows/ci.yml`
  (chart/build/deploy jobs). No app/domain changes.
- Server-side (operator, out of this repo): the k8s cluster, a `ledger-py-deploy`
  forced-command, a GHCR pull secret, DNS, and the deploy secrets/vars.
- Chart validated by `helm lint`/`template` in CI; the live rollout needs the
  server prerequisites and cannot be exercised from here.
