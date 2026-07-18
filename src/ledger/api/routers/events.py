"""Global event feed — the append-only log across all streams, for the cockpit."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from ledger.api.auth import require_api_key
from ledger.api.context import AppContext, get_context
from ledger.api.schemas import GlobalEventResponse

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(require_api_key)])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("")
async def read_events(
    context: Context,
    from_position: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[GlobalEventResponse]:
    """Events across all streams with a greater global position, in order."""
    events = await context.store.read_all(from_position=from_position, limit=limit)
    return [
        GlobalEventResponse(
            global_position=event.global_position,
            stream_type=event.stream_type,
            stream_id=event.stream_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
        )
        for event in events
    ]
