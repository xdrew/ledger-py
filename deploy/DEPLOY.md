# Deploy

A green `main` builds the image to GHCR, then **the Action itself** upgrades the
k3s release with the Helm chart from this checkout — `helm` runs on the runner and
talks to the cluster through an SSH tunnel to the API server. Nothing about this
repo lives on the server; there is no server-side clone or deploy script.

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
- **deploy** — opens an SSH tunnel to the cluster API and runs
  `helm upgrade --install ledger-py deploy/helm/ledger-py --reuse-values --set image.tag=sha-<sha>`
  from the runner, then checks the public `/readyz`. `--reuse-values` keeps the
  release's install-time config (database URL, api key, Temporal address, service
  type); only the image tag moves.

## GitHub configuration

Repo **Secrets**:

- `DEPLOY_SSH_KEY` — private key whose public key is authorized on the server,
  restricted to forwarding `127.0.0.1:6443` only (see below).
- `KUBECONFIG` — the k3s kubeconfig verbatim (its `server:` is already
  `https://127.0.0.1:6443`, which the tunnel points at); paste
  `ssh root@<host> 'cat /etc/rancher/k3s/k3s.yaml'` straight in.

Repo **Variables**:

- `DEPLOY_HOST` — server address (e.g. `46.62.174.208`).
- `DEPLOY_USER` — SSH user (e.g. `root`).

The image pushes with the built-in `GITHUB_TOKEN` (`packages: write`); the GHCR
package is public, so the cluster needs no pull secret.

## Server prerequisites (one-time provisioning, out of this repo)

This is infrastructure, done once — not part of any deploy:

1. **k3s** on the box.
2. **Postgres** reachable in-cluster with a dedicated `ledgerpy` database, and a
   **Temporal** frontend at `temporal:7233` (e.g. `temporalio/auto-setup` pointed at
   the same Postgres). Their addresses are baked into the release at install time via
   `--set secret.databaseUrl=... --set config.temporalAddress=...`.
3. **Initial install** (sets the values `--reuse-values` then carries forward):
   ```
   helm upgrade --install ledger-py deploy/helm/ledger-py \
     --set image.repository=ghcr.io/xdrew/ledger-py --set image.tag=latest \
     --set ingress.enabled=false --set service.type=NodePort \
     --set 'secret.databaseUrl=postgresql://ledger:ledger@postgres:5432/ledgerpy' \
     --set 'secret.apiKey=<key>' \
     --set 'config.temporalAddress=temporal:7233' \
     --wait
   ```
4. **Reverse proxy + TLS** — the box fronts services with nginx; add a vhost for
   `ledger-py.avelent.work` that proxies to the api Service's NodePort, with a
   Let's Encrypt cert. (No k8s ingress controller here.)
5. **Deploy key** in the deploy user's `~/.ssh/authorized_keys`, locked to opening
   the API tunnel and nothing else — no shell, no other ports:
   ```
   restrict,port-forwarding,permitopen="127.0.0.1:6443" ssh-ed25519 AAAA... deploy@ledger-py-ci
   ```
6. **DNS** `ledger-py.avelent.work` → the box.

## Manual deploy

```
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
helm upgrade --install ledger-py deploy/helm/ledger-py \
  --reuse-values --set image.tag=sha-<sha> --wait
```
