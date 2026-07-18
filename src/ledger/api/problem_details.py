"""RFC 7807 problem-details responses, driven by domain error codes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ledger.domain.shared.errors import DomainError
from ledger.eventstore.store import ConcurrencyConflict

_STATUS_BY_CODE: dict[str, int] = {
    "insufficient_funds": 422,
    "invalid_amount": 422,
    "currency_mismatch": 422,
    "unbalanced_entry": 422,
    "account_not_active": 409,
    "invalid_transition": 409,
    "account_not_empty": 409,
    "same_account_transfer": 422,
    "unknown_account": 404,
    "not_found": 404,
    "concurrency_conflict": 409,
    "duplicate_request_in_progress": 409,
    "idempotency_key_reused": 422,
    "domain_error": 400,
}


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str


def _problem(code: str, detail: str) -> tuple[int, ProblemDetail]:
    status = _STATUS_BY_CODE.get(code, 400)
    return status, ProblemDetail(
        type=f"https://errors.ledger.local/{code}",
        title=code.replace("_", " ").title(),
        status=status,
        detail=detail,
        code=code,
    )


def problem_response(code: str, detail: str) -> JSONResponse:
    """Build an ``application/problem+json`` response for a known error code.

    Public so routers can return problem details directly for conditions that are
    not raised as exceptions (e.g. idempotency-key rejections).
    """
    status, problem = _problem(code, detail)
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    return problem_response(exc.code, exc.message)


async def _handle_concurrency_conflict(_: Request, exc: ConcurrencyConflict) -> JSONResponse:
    # A lost optimistic lock on a direct write is a retryable 409, not a 500.
    return problem_response("concurrency_conflict", str(exc))


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)  # type: ignore[arg-type]
    app.add_exception_handler(ConcurrencyConflict, _handle_concurrency_conflict)  # type: ignore[arg-type]
