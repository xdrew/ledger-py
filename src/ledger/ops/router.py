"""Operational endpoints: liveness and readiness probes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from ledger.api.context import AppContext, get_context

router = APIRouter(tags=["ops"])

Context = Annotated[AppContext, Depends(get_context)]


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(response: Response, context: Context) -> dict[str, str]:
    """Ready only if the event store and Temporal are both reachable."""
    try:
        await context.store.read_all(from_position=0, limit=1)
        if not await context.gateway.check_health():
            raise RuntimeError("temporal health check returned false")
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready"}
    return {"status": "ready"}
