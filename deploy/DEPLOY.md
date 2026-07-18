# Deploy

CD mirrors the sibling `ledger` project: a green `main` builds the image to GHCR,
then rolls it onto the server's Kubernetes via the Helm chart over an SSH
forced-command, verified by `https://ledger-py.avelent.work/readyz`.

Pipeline (`.github/workflows/ci.yml`):

```
gate ─┐
      ├─ build ─┐
mutation ┘      │
chart ──────────┼─ deploy   (main only)
```

- **chart** — `helm lint` + `helm template deploy/helm/ledger-py`.
- **build** — builds `Dockerfile`; on `main` pushes `ghcr.io/xdrew/ledger-py` (tags
  `latest` + `sha-<sha>`).
- **deploy** — SSHes to the server and runs `ledger-py-deploy sha-<GITHUB_SHA>`,
  then checks the public `/readyz`.

## GitHub configuration

Repo **Secrets**:

- `DEPLOY_SSH_KEY` — private key whose public key is authorized on the server
  (restricted to the forced command below).

Repo **Variables**:

- `DEPLOY_HOST` — server address (e.g. `46.62.174.208`).
- `DEPLOY_USER` — SSH user (e.g. `deploy` or `root`).

The image pushes with the built-in `GITHUB_TOKEN` (`packages: write`); no extra
registry secret is needed in CI.

## Server prerequisites (one-time, out of this repo)

1. **Kubernetes** on the box (e.g. k3s) with an ingress controller and cert-manager
   for TLS on `ledger-py.avelent.work`.
2. **Postgres + Temporal** reachable in-cluster; set their addresses in the chart
   values / release secret (`LEDGER_DATABASE_URL`, `LEDGER_TEMPORAL_ADDRESS`).
3. **GHCR pull secret** if the image is private:
   ```
   kubectl -n ledger-py create secret docker-registry ghcr \
     --docker-server=ghcr.io --docker-username=xdrew --docker-password=<PAT-with-read:packages>
   ```
   and set `imagePullSecrets: [{ name: ghcr }]` in values.
4. **The `ledger-py-deploy` forced command** — a script on the server that takes the
   image tag, pulls the chart from this repo, and upgrades the release:
   ```sh
   #!/usr/bin/env bash
   # /usr/local/bin/ledger-py-deploy  — arg: sha-<gitsha>
   set -euo pipefail
   tag="${SSH_ORIGINAL_COMMAND##* }"; tag="${tag:-latest}"
   cd /opt/ledger-py && git fetch --all && git reset --hard origin/main
   helm upgrade --install ledger-py deploy/helm/ledger-py \
     --namespace ledger-py --create-namespace \
     --set image.tag="$tag" \
     --set secret.apiKey="$(cat /etc/ledger-py/api-key)" \
     --set secret.databaseUrl="$(cat /etc/ledger-py/database-url)" \
     --wait --timeout 5m
   ```
   Restrict the deploy key in `~/.ssh/authorized_keys` to it:
   ```
   command="/usr/local/bin/ledger-py-deploy",no-port-forwarding,no-pty ssh-ed25519 AAAA... deploy@ci
   ```
5. **DNS** `ledger-py.avelent.work` → the ingress.

## Manual deploy

```
helm upgrade --install ledger-py deploy/helm/ledger-py \
  --namespace ledger-py --create-namespace \
  --set image.tag=sha-<sha> \
  --set secret.apiKey=<key> --set secret.databaseUrl=<url> --wait
```
