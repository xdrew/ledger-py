"""Scaffold smoke tests — prove the toolchain, config, and 3.14 features are wired."""

import sys
import uuid

import pytest

from ledger.config.settings import Settings, get_settings


def test_runs_on_python_314() -> None:
    assert sys.version_info[:2] >= (3, 14)


def test_settings_load_with_defaults() -> None:
    settings = Settings()
    assert settings.temporal_task_queue == "ledger-transfers"
    assert settings.database_url.startswith("postgresql://")


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()


def test_env_prefix_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LEDGER_TEMPORAL_TASK_QUEUE", "custom-queue")
    get_settings.cache_clear()
    try:
        assert get_settings().temporal_task_queue == "custom-queue"
    finally:
        get_settings.cache_clear()


def test_stdlib_uuid7_is_time_ordered() -> None:
    # uuid7 is time-ordered: later ids sort after earlier ones.
    first = uuid.uuid7()
    second = uuid.uuid7()
    assert first < second
