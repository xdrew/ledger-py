"""RFC 7807 problem-details responses, driven by domain error codes."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ledger.domain.shared.errors import DomainError

_STATUS_BY_CODE: dict[str, int] = {
    "insufficient_funds": 422,
    "invalid_amount": 422,
    "currency_mismatch": 422,
    "unbalanced_entry": 422,
    "account_not_active": 409,
    "invalid_transition": 409,
    "account_not_empty": 409,
    "unknown_account": 404,
    "not_found": 404,
    "domain_error": 400,
}


class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    code: str


def _problem(exc: DomainError) -> tuple[int, ProblemDetail]:
    status = _STATUS_BY_CODE.get(exc.code, 400)
    return status, ProblemDetail(
        type=f"https://errors.ledger.local/{exc.code}",
        title=exc.code.replace("_", " ").title(),
        status=status,
        detail=exc.message,
        code=exc.code,
    )


async def _handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
    status, problem = _problem(exc)
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


def install_problem_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _handle_domain_error)  # type: ignore[arg-type]
