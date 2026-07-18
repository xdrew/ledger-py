"""HTTP API tests via TestClient against an in-memory context (no Temporal/DB)."""

# starlette's TestClient request methods are loosely typed (Unknown return);
# relax the resulting noise for this file only.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from httpx2 import ASGITransport, AsyncClient

from ledger.api.context import AppContext
from ledger.api.idempotency import ClaimResult, IdempotencyStore
from ledger.api.main import create_app
from ledger.config.settings import get_settings
from ledger.domain.shared.identifiers import new_account_id, new_journal_entry_id, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.transfer import Transfer
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.eventstore.store import ConcurrencyConflict
from ledger.temporal.dependencies import build_repositories
from ledger.temporal.messages import ReconciliationResolution, TransferInput

HEADERS = {"X-Api-Key": "dev-local-key"}


class FakeGateway:
    def __init__(self) -> None:
        self.started: list[TransferInput] = []
        self.resolved: list[tuple[UUID, ReconciliationResolution]] = []

    async def start(self, data: TransferInput) -> None:
        self.started.append(data)

    async def resolve(self, transfer_id: UUID, decision: ReconciliationResolution) -> None:
        self.resolved.append((transfer_id, decision))


@pytest.fixture
def context() -> tuple[AppContext, FakeGateway]:
    registry = build_event_registry()
    store = InMemoryEventStore(registry)
    gateway = FakeGateway()
    ctx = AppContext(
        settings=get_settings(),
        store=store,
        repositories=build_repositories(store, registry),
        gateway=gateway,
        idempotency=IdempotencyStore(),
    )
    return ctx, gateway


@pytest.fixture
def client(context: tuple[AppContext, FakeGateway]) -> Iterator[TestClient]:
    app = create_app()
    app.state.context = context[0]
    with TestClient(app) as test_client:
        yield test_client


class TestAuth:
    def test_missing_api_key_is_401(self, client: TestClient) -> None:
        response = client.post("/api/accounts", json={"currency": "USD"})
        assert response.status_code == 401

    def test_wrong_api_key_is_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/accounts", json={"currency": "USD"}, headers={"X-Api-Key": "not-the-key"}
        )
        assert response.status_code == 401

    def test_correct_api_key_is_accepted(self, client: TestClient) -> None:
        response = client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS)
        assert response.status_code == 201

    def test_healthz_is_open(self, client: TestClient) -> None:
        assert client.get("/healthz").status_code == 200

    def test_readyz_reports_ready(self, client: TestClient) -> None:
        response = client.get("/readyz")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_playground_served_at_root(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "ledger-core" in response.text


class TestAccounts:
    def test_open_deposit_and_read(self, client: TestClient) -> None:
        opened = client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS)
        assert opened.status_code == 201
        account_id = opened.json()["account_id"]
        assert opened.json()["status"] == "open"

        deposited = client.post(
            f"/api/accounts/{account_id}/deposit",
            json={"amount": 1000, "currency": "USD"},
            headers=HEADERS,
        )
        assert deposited.status_code == 200
        assert deposited.json()["available"] == 1000

        fetched = client.get(f"/api/accounts/{account_id}", headers=HEADERS)
        assert fetched.status_code == 200
        assert fetched.json()["total"] == 1000

    def test_currency_mismatch_is_problem_json(self, client: TestClient) -> None:
        account_id = client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS).json()[
            "account_id"
        ]
        response = client.post(
            f"/api/accounts/{account_id}/deposit",
            json={"amount": 100, "currency": "EUR"},
            headers=HEADERS,
        )
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "currency_mismatch"

    def test_unknown_account_is_404(self, client: TestClient) -> None:
        response = client.get(f"/api/accounts/{new_transfer_id()}", headers=HEADERS)
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    def test_concurrency_conflict_is_409_problem_json(
        self,
        client: TestClient,
        context: tuple[AppContext, FakeGateway],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ctx, _ = context
        account_id = client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS).json()[
            "account_id"
        ]

        async def _conflict(*_args: Any, **_kwargs: Any) -> None:
            raise ConcurrencyConflict("account", UUID(account_id), 1, 2)

        monkeypatch.setattr(ctx.repositories.accounts, "save", _conflict)
        response = client.post(
            f"/api/accounts/{account_id}/deposit",
            json={"amount": 100, "currency": "USD"},
            headers=HEADERS,
        )
        assert response.status_code == 409
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "concurrency_conflict"

    async def test_account_events_carry_correlation_and_trace(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        ctx, _ = context
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
        account_id = UUID(
            client.post(
                "/api/accounts",
                json={"currency": "USD"},
                headers={**HEADERS, "traceparent": traceparent},
            ).json()["account_id"]
        )
        stream = await ctx.store.load_stream(stream_type="account", stream_id=account_id)
        assert stream[0].metadata.correlation_id == account_id
        assert stream[0].metadata.traceparent == traceparent

    async def test_account_events_without_trace_are_null(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        ctx, _ = context
        account_id = UUID(
            client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS).json()[
                "account_id"
            ]
        )
        stream = await ctx.store.load_stream(stream_type="account", stream_id=account_id)
        assert stream[0].metadata.correlation_id == account_id
        assert stream[0].metadata.traceparent is None

    def test_statement_and_events(self, client: TestClient) -> None:
        account_id = client.post("/api/accounts", json={"currency": "USD"}, headers=HEADERS).json()[
            "account_id"
        ]
        client.post(
            f"/api/accounts/{account_id}/deposit",
            json={"amount": 500, "currency": "USD"},
            headers=HEADERS,
        )
        statement = client.get(f"/api/accounts/{account_id}/statement", headers=HEADERS)
        assert statement.status_code == 200
        assert statement.json()[0]["kind"] == "FundsDeposited"

        events = client.get(f"/api/accounts/{account_id}/events", headers=HEADERS)
        assert [e["event_type"] for e in events.json()] == [
            "AccountOpened",
            "FundsDeposited",
        ]


class TestTransfers:
    def test_create_starts_workflow(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        _, gateway = context
        body = {
            "source_account_id": str(new_transfer_id()),
            "destination_account_id": str(new_transfer_id()),
            "amount": 400,
            "currency": "USD",
        }
        response = client.post("/api/transfers", json=body, headers=HEADERS)
        assert response.status_code == 202
        assert response.json()["status"] == "initiated"
        assert len(gateway.started) == 1

    def test_idempotency_key_replays_first_response(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        _, gateway = context
        body = {
            "source_account_id": str(new_transfer_id()),
            "destination_account_id": str(new_transfer_id()),
            "amount": 400,
            "currency": "USD",
        }
        headers = {**HEADERS, "Idempotency-Key": "abc-123"}
        first = client.post("/api/transfers", json=body, headers=headers)
        second = client.post("/api/transfers", json=body, headers=headers)
        assert first.json()["transfer_id"] == second.json()["transfer_id"]
        assert len(gateway.started) == 1  # second was replayed, not re-run

    def test_idempotency_key_reused_with_different_body_is_422(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        _, gateway = context
        headers = {**HEADERS, "Idempotency-Key": "reuse-1"}
        base = {
            "source_account_id": str(new_transfer_id()),
            "destination_account_id": str(new_transfer_id()),
            "amount": 400,
            "currency": "USD",
        }
        first = client.post("/api/transfers", json=base, headers=headers)
        assert first.status_code == 202
        second = client.post("/api/transfers", json={**base, "amount": 999}, headers=headers)
        assert second.status_code == 422
        assert second.json()["code"] == "idempotency_key_reused"
        assert len(gateway.started) == 1  # the mismatched request started nothing

    async def test_get_transfer(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        ctx, _ = context
        transfer = Transfer.initiate(
            new_transfer_id(),
            new_transfer_id(),
            new_transfer_id(),
            Money(amount=250, currency="USD"),
        )
        assert transfer.transfer_id is not None
        await ctx.repositories.transfers.save(transfer.transfer_id, transfer)

        response = client.get(f"/api/transfers/{transfer.transfer_id}", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["status"] == "initiated"
        assert response.json()["amount"] == 250

    def test_get_unknown_transfer_is_404(self, client: TestClient) -> None:
        response = client.get(f"/api/transfers/{new_transfer_id()}", headers=HEADERS)
        assert response.status_code == 404

    async def _park(self, ctx: AppContext) -> UUID:
        transfer = Transfer.initiate(
            new_transfer_id(), new_account_id(), new_account_id(), Money(amount=400, currency="USD")
        )
        transfer.mark_held()
        transfer.mark_posted(new_journal_entry_id())
        transfer.park_for_reconciliation("credit failed after debit")
        assert transfer.transfer_id is not None
        await ctx.repositories.transfers.save(transfer.transfer_id, transfer)
        return transfer.transfer_id

    async def test_resolve_parked_transfer_signals_gateway(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        ctx, gateway = context
        transfer_id = await self._park(ctx)
        response = client.post(
            f"/api/transfers/{transfer_id}/resolve",
            json={"resolution": "refund_source"},
            headers=HEADERS,
        )
        assert response.status_code == 202
        assert gateway.resolved == [(transfer_id, ReconciliationResolution.REFUND_SOURCE)]

    async def test_resolve_non_parked_transfer_is_409(
        self, client: TestClient, context: tuple[AppContext, FakeGateway]
    ) -> None:
        ctx, gateway = context
        transfer = Transfer.initiate(
            new_transfer_id(), new_account_id(), new_account_id(), Money(amount=400, currency="USD")
        )
        assert transfer.transfer_id is not None
        await ctx.repositories.transfers.save(transfer.transfer_id, transfer)
        response = client.post(
            f"/api/transfers/{transfer.transfer_id}/resolve",
            json={"resolution": "retry_credit"},
            headers=HEADERS,
        )
        assert response.status_code == 409
        assert response.json()["code"] == "invalid_transition"
        assert gateway.resolved == []


class _ClosableStore(InMemoryEventStore):
    def __init__(self) -> None:
        super().__init__(build_event_registry())
        self.closed = 0

    async def aclose(self) -> None:
        self.closed += 1


def _ctx_with(store: Any) -> AppContext:
    registry = build_event_registry()
    mem = InMemoryEventStore(registry)
    return AppContext(
        settings=get_settings(),
        store=store,
        repositories=build_repositories(mem, registry),
        gateway=FakeGateway(),
        idempotency=IdempotencyStore(),
    )


class TestLifecycle:
    async def test_aclose_closes_store_that_supports_it(self) -> None:
        store = _ClosableStore()
        await _ctx_with(store).aclose()
        assert store.closed == 1

    async def test_aclose_is_noop_for_plain_store(self) -> None:
        # In-memory store has no aclose; closing the context must not raise.
        await _ctx_with(InMemoryEventStore(build_event_registry())).aclose()

    def test_lifespan_closes_owned_context(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store = _ClosableStore()

        async def _build(_settings: Any) -> AppContext:
            return _ctx_with(store)

        monkeypatch.setattr("ledger.api.main.build_runtime_context", _build)
        app = create_app()  # no injected context → lifespan builds and owns it
        with TestClient(app):
            pass
        assert store.closed == 1

    def test_lifespan_leaves_injected_context_open(self) -> None:
        store = _ClosableStore()
        app = create_app()
        app.state.context = _ctx_with(store)  # injected → not owned
        with TestClient(app):
            pass
        assert store.closed == 0


class TestIdempotencyStore:
    def test_claim_lifecycle(self) -> None:
        store = IdempotencyStore()

        result, response = store.claim("k", "route", "fp")
        assert result is ClaimResult.NEW and response is None

        in_progress, _ = store.claim("k", "route", "fp")
        assert in_progress is ClaimResult.IN_PROGRESS

        mismatch, _ = store.claim("k", "route", "different")
        assert mismatch is ClaimResult.MISMATCH

        store.complete("k", "route", 202, {"x": 1})
        replay, stored = store.claim("k", "route", "fp")
        assert replay is ClaimResult.REPLAY
        assert stored is not None and stored.body == {"x": 1}

    def test_discard_releases_reservation(self) -> None:
        store = IdempotencyStore()
        store.claim("k", "route", "fp")
        store.discard("k", "route")
        result, _ = store.claim("k", "route", "fp")
        assert result is ClaimResult.NEW  # reservation was released, key reusable


class TestIdempotencyConcurrency:
    async def test_concurrent_same_key_starts_saga_once(self) -> None:
        registry = build_event_registry()
        store = InMemoryEventStore(registry)
        entered = asyncio.Event()
        release = asyncio.Event()
        started: list[TransferInput] = []

        class BlockingGateway:
            async def start(self, data: TransferInput) -> None:
                started.append(data)
                entered.set()
                await release.wait()

            async def resolve(self, transfer_id: UUID, decision: ReconciliationResolution) -> None:
                raise AssertionError("resolve not expected in this test")

        ctx = AppContext(
            settings=get_settings(),
            store=store,
            repositories=build_repositories(store, registry),
            gateway=BlockingGateway(),
            idempotency=IdempotencyStore(),
        )
        app = create_app()
        app.state.context = ctx

        body = {
            "source_account_id": str(new_transfer_id()),
            "destination_account_id": str(new_transfer_id()),
            "amount": 400,
            "currency": "USD",
        }
        headers = {**HEADERS, "Idempotency-Key": "race-1"}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:

            async def fire() -> Any:
                return await http.post("/api/transfers", json=body, headers=headers)

            first = asyncio.create_task(fire())
            await entered.wait()  # first request has claimed the key and is in flight
            second = await fire()  # concurrent duplicate while the first is in flight
            release.set()
            first_response = await first

        assert len(started) == 1  # the saga was started exactly once
        statuses = {first_response.status_code, second.status_code}
        assert statuses == {202, 409}
        duplicate = second if second.status_code == 409 else first_response
        assert duplicate.json()["code"] == "duplicate_request_in_progress"
