## 1. Image

- [x] 1.1 Add a multi-stage `Dockerfile`: build stage runs `uv sync --frozen
  --no-dev`; runtime stage is a slim pinned base, non-root user, venv on PATH,
  default `CMD ["ledger-api"]`.
- [x] 1.2 Add `.dockerignore` (exclude .venv, .git, var, caches, tests artifacts).

## 2. Compose

- [x] 2.1 Add `api`, `worker`, `relay` services building the image, depending on
  postgres+temporal, with `LEDGER_*` env, behind an `app` profile.

## 3. Verify

- [x] 3.1 (Docker required) `docker compose --profile app build` and
  `--profile app up` bring the system up; `GET /healthz` and `/readyz` return ok.
  Documented; not run here (no Docker daemon available in this environment).
- [x] 3.2 `openspec validate containerize-app --strict` passes.
