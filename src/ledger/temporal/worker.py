"""Temporal worker entrypoint — hosts the transfer workflow and its activities."""

import asyncio
import logging

from temporalio.worker import Worker

from ledger.config.settings import Settings, get_settings
from ledger.eventstore.factory import open_event_store
from ledger.eventstore.registry import build_event_registry
from ledger.observability.setup import configure_observability
from ledger.temporal.activities.transfer_activities import TransferActivities
from ledger.temporal.client import connect
from ledger.temporal.dependencies import build_repositories
from ledger.temporal.workflows.transfer_workflow import TransferWorkflow

_log = logging.getLogger(__name__)


async def run_worker(settings: Settings) -> None:
    registry = build_event_registry()
    store = await open_event_store(settings, registry)
    repos = build_repositories(store, registry)
    activities = TransferActivities(
        accounts=repos.accounts,
        journals=repos.journals,
        transfers=repos.transfers,
    )

    client = await connect(settings)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[TransferWorkflow],
        activities=activities.all_activities(),
    )
    _log.info("worker started on task queue %s", settings.temporal_task_queue)
    await worker.run()


def main() -> None:
    settings = get_settings()
    configure_observability(settings)
    asyncio.run(run_worker(settings))


if __name__ == "__main__":
    main()
