"""Runtime container for the account read models (the CQRS query side).

Holds the balances and statement projections and a :class:`ProjectionRunner` that
feeds them from the global event log. Reads catch up on demand (``catch_up``), so a
query reflects every event that occurred before it — a read-your-writes projection
that is rebuilt from the log on each process start.

The continuous, durable, cross-instance variant (a background runner writing a
Postgres read model) is the production evolution; this keeps the read side genuinely
live and queryable in-process.
"""

import asyncio

from ledger.domain.shared.identifiers import AccountId
from ledger.eventstore.serialization import EventRegistry
from ledger.eventstore.store import EventStore
from ledger.projections.read_models import (
    AccountBalancesProjection,
    AccountBalanceView,
    AccountStatementProjection,
    StatementLine,
)
from ledger.projections.runner import InMemoryCheckpointStore, ProjectionRunner

_RUNNER_NAME = "account-read-models"


class ReadModels:
    def __init__(self, store: EventStore, registry: EventRegistry) -> None:
        self._balances = AccountBalancesProjection(registry)
        self._statements = AccountStatementProjection()
        self._runner = ProjectionRunner(
            store=store,
            checkpoints=InMemoryCheckpointStore(),
            name=_RUNNER_NAME,
            projectors=[self._balances, self._statements],
        )
        # Serialize drains: the projectors apply events non-idempotently (+=), so two
        # concurrent catch-ups reading the same batch (the store's read yields) would
        # double-apply. The lock makes overlapping reads apply each event exactly once.
        self._lock = asyncio.Lock()

    async def catch_up(self) -> None:
        """Process any events since the last read so the models are current."""
        async with self._lock:
            await self._runner.drain()

    async def balance_of(self, account_id: AccountId) -> AccountBalanceView | None:
        await self.catch_up()
        return self._balances.balance_of(account_id)

    async def statement_of(self, account_id: AccountId) -> list[StatementLine]:
        await self.catch_up()
        return self._statements.statement_of(account_id)


def build_read_models(store: EventStore, registry: EventRegistry) -> ReadModels:
    return ReadModels(store, registry)
