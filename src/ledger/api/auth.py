"""API-key authentication (``X-Api-Key`` header)."""

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from ledger.config.settings import get_settings


async def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    # Constant-time compare so a wrong key cannot be recovered from response
    # timing; a missing header is rejected without short-circuiting on length.
    expected = get_settings().api_key
    if x_api_key is None or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing api key"
        )
