# ledger-py task runner. Requires `just` (https://github.com/casey/just) and `uv`.
# Everything runs through uv so the pinned 3.14 interpreter + lockfile are authoritative.

set dotenv-load := true

default:
    @just --list

# Install/refresh the virtualenv from the lockfile (incl. dev tools).
sync:
    uv sync --extra dev

# Bring up the local infra stack (Postgres, Temporal, OTel, Grafana).
up:
    docker compose up -d
    @echo "Temporal UI  -> http://localhost:8233"
    @echo "Grafana      -> http://localhost:3001"

down:
    docker compose down

# Wipe infra volumes (fresh Postgres + Temporal).
nuke:
    docker compose down -v

# Apply the event-store schema to LEDGER_DATABASE_URL.
migrate:
    uv run ledger-migrate

# Run the Temporal worker (workflows + activities).
worker:
    uv run ledger-worker

# Run the FastAPI app.
api:
    uv run ledger-api

# Quality gate.
fmt:
    uv run ruff format src tests

lint:
    uv run ruff check src tests

typecheck:
    uv run pyright

test *ARGS:
    uv run pytest {{ARGS}}

# Tests with coverage report.
cov:
    uv run pytest --cov=ledger --cov-report=term-missing

# Mutation testing over the domain (Infection analogue). Fast; enforces a kill-rate floor.
mutation floor="0.75":
    uv run python scripts/mutation_gate.py {{floor}}

# Full gate — run before every commit.
check: lint typecheck test
    uv run ruff format --check src tests
