"""Account endpoints: open, deposit, read balance / statement / events."""

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from ledger.api.auth import require_api_key
from ledger.api.context import AppContext, get_context
from ledger.api.idempotency import ClaimResult
from ledger.api.problem_details import problem_response
from ledger.api.schemas import (
    AccountResponse,
    DepositRequest,
    EventResponse,
    OpenAccountRequest,
    StatementLineResponse,
)
from ledger.domain.accounts.account import Account
from ledger.domain.accounts.events import ACCOUNT_STREAM
from ledger.domain.shared.errors import NotFound
from ledger.domain.shared.identifiers import AccountId, new_account_id
from ledger.domain.shared.money import Money
from ledger.eventstore.records import EventMetadata, StoredEvent

router = APIRouter(
    prefix="/api/accounts", tags=["accounts"], dependencies=[Depends(require_api_key)]
)

Context = Annotated[AppContext, Depends(get_context)]

_DEPOSIT_ROUTE = "POST /api/accounts/{id}/deposit"


def _deposit_fingerprint(account_id: AccountId, body: DepositRequest) -> str:
    canonical = json.dumps(
        {"account_id": str(account_id), **body.model_dump(mode="json")}, sort_keys=True
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _account_response(account_id: AccountId, account: Account) -> AccountResponse:
    return AccountResponse(
        account_id=account_id,
        currency=account.currency,
        status=account.status,
        available=account.available.amount,
        reserved=account.reserved.amount,
        total=account.available.amount + account.reserved.amount,
    )


def _event_response(event: StoredEvent) -> EventResponse:
    return EventResponse(
        global_position=event.global_position,
        version=event.version,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        payload=event.payload,
    )


async def _load_or_404(context: AppContext, account_id: AccountId) -> Account:
    account = await context.repositories.accounts.load(account_id)
    if account is None:
        raise NotFound(f"account {account_id} not found")
    return account


@router.post("", status_code=201)
async def open_account(
    body: OpenAccountRequest,
    context: Context,
    traceparent: Annotated[str | None, Header()] = None,
) -> AccountResponse:
    account_id = new_account_id()
    account = Account.open(account_id, body.currency)
    await context.repositories.accounts.save(
        account_id, account, EventMetadata(correlation_id=account_id, traceparent=traceparent)
    )
    return _account_response(account_id, account)


@router.post("/{account_id}/deposit", response_model=AccountResponse)
async def deposit(
    account_id: AccountId,
    body: DepositRequest,
    context: Context,
    idempotency_key: Annotated[str | None, Header()] = None,
    traceparent: Annotated[str | None, Header()] = None,
) -> AccountResponse | JSONResponse:
    if idempotency_key is not None:
        result, stored = context.idempotency.claim(
            idempotency_key, _DEPOSIT_ROUTE, _deposit_fingerprint(account_id, body)
        )
        match result:
            case ClaimResult.REPLAY if stored is not None:
                return JSONResponse(status_code=stored.status_code, content=stored.body)
            case ClaimResult.IN_PROGRESS:
                return problem_response(
                    "duplicate_request_in_progress",
                    "a deposit with this idempotency key is already in progress",
                )
            case ClaimResult.MISMATCH:
                return problem_response(
                    "idempotency_key_reused",
                    "idempotency key was reused with a different request",
                )
            case _:
                pass

    try:
        account = await _load_or_404(context, account_id)
        account.deposit(Money(amount=body.amount, currency=body.currency))
        await context.repositories.accounts.save(
            account_id, account, EventMetadata(correlation_id=account_id, traceparent=traceparent)
        )
    except Exception:
        if idempotency_key is not None:
            context.idempotency.discard(idempotency_key, _DEPOSIT_ROUTE)
        raise

    response = _account_response(account_id, account)
    if idempotency_key is not None:
        context.idempotency.complete(
            idempotency_key, _DEPOSIT_ROUTE, 200, response.model_dump(mode="json")
        )
    return response


@router.get("/{account_id}")
async def get_account(account_id: AccountId, context: Context) -> AccountResponse:
    account = await _load_or_404(context, account_id)
    return _account_response(account_id, account)


@router.post("/{account_id}/freeze")
async def freeze_account(
    account_id: AccountId,
    context: Context,
    traceparent: Annotated[str | None, Header()] = None,
) -> AccountResponse:
    account = await _load_or_404(context, account_id)
    account.freeze()
    await context.repositories.accounts.save(
        account_id, account, EventMetadata(correlation_id=account_id, traceparent=traceparent)
    )
    return _account_response(account_id, account)


@router.post("/{account_id}/close")
async def close_account(
    account_id: AccountId,
    context: Context,
    traceparent: Annotated[str | None, Header()] = None,
) -> AccountResponse:
    account = await _load_or_404(context, account_id)
    account.close()
    await context.repositories.accounts.save(
        account_id, account, EventMetadata(correlation_id=account_id, traceparent=traceparent)
    )
    return _account_response(account_id, account)


@router.get("/{account_id}/balance")
async def get_balance(account_id: AccountId, context: Context) -> AccountResponse:
    """Balance served from the projection read model (catches up on read)."""
    view = await context.read_models.balance_of(account_id)
    if view is None:
        raise NotFound(f"account {account_id} not found")
    return AccountResponse(
        account_id=account_id,
        currency=view.currency,
        status=view.status,
        available=view.available,
        reserved=view.reserved,
        total=view.total,
    )


@router.get("/{account_id}/statement")
async def get_statement(account_id: AccountId, context: Context) -> list[StatementLineResponse]:
    await _load_or_404(context, account_id)
    lines = await context.read_models.statement_of(account_id)
    return [
        StatementLineResponse(
            global_position=line.global_position,
            kind=line.kind,
            amount=line.amount,
            currency=line.currency,
            occurred_at=line.occurred_at,
        )
        for line in lines
    ]


@router.get("/{account_id}/events")
async def get_events(account_id: AccountId, context: Context) -> list[EventResponse]:
    await _load_or_404(context, account_id)
    events = await context.store.load_stream(stream_type=ACCOUNT_STREAM, stream_id=account_id)
    return [_event_response(event) for event in events]
