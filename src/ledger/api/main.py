"""FastAPI application assembly."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from ledger.api.context import build_runtime_context
from ledger.api.problem_details import install_problem_handlers
from ledger.api.routers import accounts, transfers
from ledger.config.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Tests inject app.state.context up front; otherwise build it (connects Temporal).
    if getattr(app.state, "context", None) is None:
        app.state.context = await build_runtime_context(get_settings())
    yield


async def _healthz() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    app = FastAPI(title="ledger-core", version="0.1.0", lifespan=lifespan)
    install_problem_handlers(app)
    app.include_router(accounts.router)
    app.include_router(transfers.router)
    app.add_api_route("/healthz", _healthz, methods=["GET"], tags=["ops"])
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run("ledger.api.main:app", host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
