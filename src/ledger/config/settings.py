"""Application configuration.

All settings are read from the environment (prefix ``LEDGER_``) or a local
``.env`` file. A single :class:`Settings` instance is resolved lazily via
:func:`get_settings` and cached for process lifetime.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated process configuration."""

    model_config = SettingsConfigDict(
        env_prefix="LEDGER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Postgres (app state: events, projections, idempotency) ---
    database_url: str = "postgresql://ledger:ledger@localhost:5432/ledger"
    db_pool_min_size: int = 1
    db_pool_max_size: int = 10

    # --- Temporal ---
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "ledger-transfers"

    # --- API ---
    api_host: str = "0.0.0.0"  # bind-all is intended inside the container
    api_port: int = 8000
    api_key: str = Field(default="dev-local-key", repr=False)

    # --- Observability ---
    # None by default so tests / local runs need no collector; set in deploy.
    otel_exporter_otlp_endpoint: str | None = None
    service_name: str = "ledger-core"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings, resolved once and cached."""
    return Settings()
