"""Transfer endpoints: start a saga, read its status / events."""

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
    CreateTransferRequest,
    EventResponse,
    ResolveTransferRequest,
    TransferAccepted,
    TransferResponse,
)
from ledger.domain.shared.errors import InvalidTransition, NotFound
from ledger.domain.shared.identifiers import TransferId, new_transfer_id
from ledger.domain.shared.money import Money
from ledger.domain.transfers.events import TRANSFER_STREAM
from ledger.domain.transfers.transfer import Transfer, TransferStatus
from ledger.eventstore.records import StoredEvent
from ledger.temporal.messages import TransferInput

router = APIRouter(
    prefix="/api/transfers", tags=["transfers"], dependencies=[Depends(require_api_key)]
)

Context = Annotated[AppContext, Depends(get_context)]
_ROUTE = "POST /api/transfers"


def _fingerprint(body: CreateTransferRequest) -> str:
    """Stable hash of the semantic request (excludes the server-minted id)."""
    canonical = json.dumps(body.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    traceparent: Annotated[str | None, Header()] = None,
) -> TransferAccepted | JSONResponse:
    if idempotency_key is not None:
        # Claim the key atomically *before* any work so concurrent duplicates
        # cannot each start a saga (claim() does no await — atomic under the loop).
        result, stored = await context.idempotency.claim(
            idempotency_key, _ROUTE, _fingerprint(body)
        )
        match result:
            case ClaimResult.REPLAY if stored is not None:
                return JSONResponse(status_code=stored.status_code, content=stored.body)
            case ClaimResult.IN_PROGRESS:
                return problem_response(
                    "duplicate_request_in_progress",
                    "a request with this idempotency key is already in progress",
                )
            case ClaimResult.MISMATCH:
                return problem_response(
                    "idempotency_key_reused",
                    "idempotency key was reused with a different request",
                )
            case _:  # NEW — we hold the claim and must complete or discard it
                pass

    transfer_id = new_transfer_id()
    try:
        await context.gateway.start(
            TransferInput(
                transfer_id=transfer_id,
                source_account_id=body.source_account_id,
                destination_account_id=body.destination_account_id,
                amount=Money(amount=body.amount, currency=body.currency),
                traceparent=traceparent,
            )
        )
    except Exception:
        if idempotency_key is not None:
            await context.idempotency.discard(idempotency_key, _ROUTE)
        raise

    accepted = TransferAccepted(transfer_id=transfer_id, status="initiated")
    if idempotency_key is not None:
        await context.idempotency.complete(
            idempotency_key, _ROUTE, 202, accepted.model_dump(mode="json")
        )
    return accepted


@router.post("/{transfer_id}/resolve", status_code=202, response_model=TransferAccepted)
async def resolve_transfer(
    transfer_id: TransferId, body: ResolveTransferRequest, context: Context
) -> TransferAccepted:
    transfer = await context.repositories.transfers.load(transfer_id)
    if transfer is None:
        raise NotFound(f"transfer {transfer_id} not found")
    if transfer.status is not TransferStatus.NEEDS_RECONCILIATION:
        raise InvalidTransition(
            f"transfer {transfer_id} is {transfer.status.value}, not needs_reconciliation"
        )
    await context.gateway.resolve(transfer_id, body.resolution)
    return TransferAccepted(transfer_id=transfer_id, status="resolving")


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
