"""Transfer gateway — the API's seam onto Temporal.

A Protocol so the API depends on an abstraction (easy to fake in tests); the
Temporal implementation starts the workflow with a deterministic id, which also
gives command-level idempotency (a duplicate start is rejected by the server).
"""

from typing import Protocol

from temporalio.client import Client

from ledger.temporal.messages import TransferInput
from ledger.temporal.workflows.transfer_workflow import TransferWorkflow


class TransferGateway(Protocol):
    async def start(self, data: TransferInput) -> None: ...


class TemporalTransferGateway:
    def __init__(self, client: Client, task_queue: str) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start(self, data: TransferInput) -> None:
        await self._client.start_workflow(
            TransferWorkflow.run,
            data,
            id=f"transfer-{data.transfer_id}",
            task_queue=self._task_queue,
        )
