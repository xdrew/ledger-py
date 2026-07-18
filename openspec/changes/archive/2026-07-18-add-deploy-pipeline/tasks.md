## 1. Helm chart (deploy/helm/ledger-py)

- [x] 1.1 Chart.yaml, values.yaml, _helpers.tpl (LEDGER_* config/secret data blocks).
- [x] 1.2 Deployments: api (port 8000, /healthz + /readyz probes), worker, relay —
  `command: [ledger-api|ledger-worker|ledger-relay]`, native SIGTERM.
- [x] 1.3 Migration Job as pre-install/pre-upgrade hook with hook-scoped config/secret.
- [x] 1.4 Service (api), api HPA, PDB, optional ingress (host ledger-py.avelent.work).

## 2. CI (.github/workflows/ci.yml)

- [x] 2.1 chart job: `helm lint` + `helm template` the chart.
- [x] 2.2 build job: build the image; on main push to `ghcr.io/<owner>/ledger-py`
  (tags latest + sha), gha cache.
- [x] 2.3 deploy job (main only, after gate+mutation+build): SSH forced-command
  `ledger-py-deploy sha-<SHA>`; verify `https://ledger-py.avelent.work/readyz`.

## 3. Docs

- [x] 3.1 `deploy/DEPLOY.md`: server-side prerequisites (cluster, ledger-py-deploy
  forced command, GHCR pull secret, DNS) and required GitHub secrets/vars.

## 4. Gate

- [x] 4.1 CI YAML is valid; chart lints/renders in CI.
- [x] 4.2 `openspec validate add-deploy-pipeline --strict` passes.
