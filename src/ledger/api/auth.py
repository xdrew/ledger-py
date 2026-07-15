"""API-key authentication (``X-Api-Key`` header)."""

from typing import Annotated

from fastapi import Header, HTTPException, status

from ledger.config.settings import get_settings


async def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    if x_api_key != get_settings().api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing api key"
        )
