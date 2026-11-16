"""ProDesk API entrypoint."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, correlation_id_var, get_logger, request_id_var
from app.workers import dispatch as _dispatch  # noqa: F401  (registers after-commit job hooks)

configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
log = get_logger("prodesk.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.validate_for_runtime()
    from app.db.session import SessionLocal
    from app.services.rbac import sync_system_roles

    try:
        with SessionLocal() as db:
            sync_system_roles(db)
            db.commit()
    except Exception:
        log.exception("rbac_sync_failed_on_startup (run migrations?)")
    log.info(
        "startup",
        extra={
            "env": settings.APP_ENV,
            "whatsapp": settings.WHATSAPP_PROVIDER,
            "ai": settings.AI_PROVIDER,
            "payments": settings.PAYMENT_PROVIDER,
            "storage": settings.STORAGE_PROVIDER,
        },
    )
    yield


app = FastAPI(
    title="ProDesk API",
    version="1.0.0",
    description="Practice management + client automation for CA firms. WhatsApp-first; the ProDesk database is the source of truth.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    rid = rid[:64]
    cid = (request.headers.get("x-correlation-id") or rid)[:64]
    t_rid, t_cid = request_id_var.set(rid), correlation_id_var.set(cid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(t_rid)
        correlation_id_var.reset(t_cid)
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if not request.url.path.startswith(("/docs", "/redoc")):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    path = request.url.path
    if not path.startswith("/health"):
        # Paths with tokens (signed files, delivery links) are not logged verbatim.
        safe_path = (
            "/api/v1/files/[token]"
            if path.startswith("/api/v1/files/")
            else ("/api/v1/portal/link/[token]" if path.startswith("/api/v1/portal/link/") else path)
        )
        log.info(
            "request", extra={"method": request.method, "path": safe_path, "status": response.status_code, "ms": elapsed, "request_id": rid}
        )
    return response


app.include_router(health_router)
app.include_router(api_router)
