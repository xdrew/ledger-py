"""HTTP API tests via TestClient against an in-memory context (no Temporal/DB)."""

# starlette's TestClient request methods are loosely typed (Unknown return);
# relax the resulting noise for this file only.
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from ledger.api.context import AppContext
from ledger.api.idempotency import IdempotencyStore
from ledger.api.main import create_app
from ledger.config.settings import get_settings
from ledger.domain.shared.identifiers import new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.transfer import Transfer
from ledger.eventstore.memory import InMemoryEventStore
from ledger.eventstore.registry import build_event_registry
from ledger.temporal.dependencies import build_repositories
from ledger.temporal.messages import TransferInput

HEADERS = {"X-Api-Key": "dev-local-key"}


class FakeGateway:
    def __init__(self) -> None:
        self.started: list[TransferInput] = []

    async def start(self, data: TransferInput) -> None:
        self.started.append(data)


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

    def test_idempotency_key_dedups(
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
        assert len(gateway.started) == 1  # second was replayed from cache

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
