"""Serves the self-contained playground page at the app root."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["showcase"])

_PAGE = (Path(__file__).parent / "playground.html").read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def playground() -> HTMLResponse:
    return HTMLResponse(_PAGE)
