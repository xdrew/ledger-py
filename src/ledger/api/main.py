"""FastAPI application assembly."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from ledger.api.context import build_runtime_context
from ledger.api.problem_details import install_problem_handlers
from ledger.api.routers import accounts, transfers
from ledger.config.settings import Settings, get_settings
from ledger.observability.setup import configure_observability
from ledger.ops.router import router as ops_router
from ledger.showcase.router import router as showcase_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Tests inject app.state.context up front; otherwise build it (connects Temporal).
    owns_context = getattr(app.state, "context", None) is None
    if owns_context:
        app.state.context = await build_runtime_context(get_settings())
    try:
        yield
    finally:
        # Only close what we opened; a test-injected context is left untouched.
        if owns_context:
            await app.state.context.aclose()


def _instrument(app: FastAPI, settings: Settings) -> None:
    if settings.otel_exporter_otlp_endpoint:
        FastAPIInstrumentor.instrument_app(app)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_observability(settings)
    app = FastAPI(title="ledger-core", version="0.1.0", lifespan=lifespan)
    install_problem_handlers(app)
    app.include_router(accounts.router)
    app.include_router(transfers.router)
    app.include_router(ops_router)
    app.include_router(showcase_router)
    _instrument(app, settings)
    return app


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run("ledger.api.main:app", host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
