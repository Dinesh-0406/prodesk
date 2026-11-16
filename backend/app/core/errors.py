"""Application error hierarchy and consistent JSON error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_var

log = get_logger(__name__)


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str = "", *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code.replace("_", " ").title()
        if code:
            self.code = code
        self.details = details


class NotFound(AppError):
    """Also used for cross-tenant access so resource existence is never leaked."""

    status_code = 404
    code = "NOT_FOUND"


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_FAILED"


class RateLimited(AppError):
    status_code = 429
    code = "RATE_LIMITED"


class ProviderError(AppError):
    status_code = 502
    code = "PROVIDER_ERROR"


def _body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}, "request_id": request_id_var.get()}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return JSONResponse(status_code=422, content=_body("VALIDATION_FAILED", "Request validation failed", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_body("HTTP_ERROR", str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", extra={"error_type": type(exc).__name__})
        return JSONResponse(status_code=500, content=_body("INTERNAL_ERROR", "An unexpected error occurred"))
