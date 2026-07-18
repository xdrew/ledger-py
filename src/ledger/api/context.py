"""Application context — the runtime dependencies wired once and shared per app."""

from dataclasses import dataclass

from fastapi import Request

from ledger.api.gateway import TemporalTransferGateway, TransferGateway
from ledger.api.idempotency import IdempotencyStore
from ledger.config.settings import Settings, get_settings
from ledger.eventstore.factory import open_event_store
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.store import EventStore
from ledger.temporal.client import connect
from ledger.temporal.dependencies import LedgerRepositories, build_repositories


@dataclass(frozen=True, slots=True)
class AppContext:
    settings: Settings
    store: EventStore
    repositories: LedgerRepositories
    gateway: TransferGateway
    idempotency: IdempotencyStore

    async def aclose(self) -> None:
        """Release owned infrastructure resources (the event-store pool)."""
        close = getattr(self.store, "aclose", None)
        if close is not None:
            await close()


async def build_runtime_context(settings: Settings) -> AppContext:
    registry = build_event_registry()
    store = await open_event_store(settings, registry)
    repositories = build_repositories(store, registry)
    client = await connect(settings)
    gateway = TemporalTransferGateway(client, settings.temporal_task_queue)
    return AppContext(
        settings=settings,
        store=store,
        repositories=repositories,
        gateway=gateway,
        idempotency=IdempotencyStore(),
    )


def get_context(request: Request) -> AppContext:
    context: AppContext = request.app.state.context
    return context


def get_settings_dep() -> Settings:
    return get_settings()
