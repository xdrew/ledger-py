"""Transfer endpoints: start a saga, read its status / events."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from ledger.api.auth import require_api_key
from ledger.api.context import AppContext, get_context
from ledger.api.schemas import (
    CreateTransferRequest,
    EventResponse,
    TransferAccepted,
    TransferResponse,
)
from ledger.domain.shared.errors import NotFound
from ledger.domain.shared.identifiers import TransferId, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import TRANSFER_STREAM
from ledger.domain.transfers.transfer import Transfer
from ledger.eventstore.records import StoredEvent
from ledger.temporal.messages import TransferInput

router = APIRouter(
    prefix="/api/transfers", tags=["transfers"], dependencies=[Depends(require_api_key)]
)

Context = Annotated[AppContext, Depends(get_context)]
_ROUTE = "POST /api/transfers"


def _event_response(event: StoredEvent) -> EventResponse:
    return EventResponse(
        global_position=event.global_position,
        version=event.version,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        payload=event.payload,
    )


def _transfer_response(transfer_id: TransferId, transfer: Transfer) -> TransferResponse:
    amount = transfer.amount
    return TransferResponse(
        transfer_id=transfer_id,
        status=transfer.status,
        source_account_id=transfer.source_account_id,
        destination_account_id=transfer.destination_account_id,
        amount=amount.amount if amount is not None else None,
        currency=amount.currency if amount is not None else None,
        journal_entry_id=transfer.journal_entry_id,
        failure_reason=transfer.failure_reason,
    )


@router.post("", status_code=202, response_model=TransferAccepted)
async def create_transfer(
    body: CreateTransferRequest,
    context: Context,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> TransferAccepted | JSONResponse:
    if idempotency_key is not None:
        cached = context.idempotency.recall(idempotency_key, _ROUTE)
        if cached is not None:
            return JSONResponse(status_code=cached.status_code, content=cached.body)

    transfer_id = new_transfer_id()
    await context.gateway.start(
        TransferInput(
            transfer_id=transfer_id,
            source_account_id=body.source_account_id,
            destination_account_id=body.destination_account_id,
            amount=Money(amount=body.amount, currency=body.currency),
        )
    )
    accepted = TransferAccepted(transfer_id=transfer_id, status="initiated")
    if idempotency_key is not None:
        context.idempotency.remember(idempotency_key, _ROUTE, 202, accepted.model_dump(mode="json"))
    return accepted


@router.get("/{transfer_id}")
async def get_transfer(transfer_id: TransferId, context: Context) -> TransferResponse:
    transfer = await context.repositories.transfers.load(transfer_id)
    if transfer is None:
        raise NotFound(f"transfer {transfer_id} not found")
    return _transfer_response(transfer_id, transfer)


@router.get("/{transfer_id}/events")
async def get_transfer_events(transfer_id: TransferId, context: Context) -> list[EventResponse]:
    events = await context.store.load_stream(stream_type=TRANSFER_STREAM, stream_id=transfer_id)
    if not events:
        raise NotFound(f"transfer {transfer_id} not found")
    return [_event_response(event) for event in events]
