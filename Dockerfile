# syntax=docker/dockerfile:1

# --- build stage: install the project into a venv with uv (frozen lockfile) ---
FROM python:3.14-slim-bookworm AS build

# uv provides reproducible, fast installs from the committed uv.lock.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# --- runtime stage: slim, non-root, venv on PATH ---
FROM python:3.14-slim-bookworm AS runtime

RUN useradd --create-home --uid 10001 ledger
WORKDIR /app

COPY --from=build --chown=ledger:ledger /app /app
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1

USER ledger
EXPOSE 8000

# Default to the API; override the command for worker / relay / migrate.
CMD ["ledger-api"]
