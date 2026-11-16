from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import engine
from app.integrations.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok", "service": "prodesk-api"}


@router.get("/health/ready")
def ready() -> JSONResponse:
    """Readiness: verifies PostgreSQL, Redis, storage, and reports provider modes."""
    checks: dict[str, Any] = {}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
            rev = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks["database"] = {"ok": True, "migration": rev}
    except Exception as e:
        checks["database"] = {"ok": False, "error": type(e).__name__}
    try:
        checks["redis"] = {"ok": bool(get_redis().ping())}
    except Exception as e:
        checks["redis"] = {"ok": False, "error": type(e).__name__}
    try:
        checks["storage"] = {"ok": get_storage().healthcheck(), "provider": settings.STORAGE_PROVIDER}
    except Exception as e:
        checks["storage"] = {"ok": False, "error": type(e).__name__}
    checks["providers"] = {
        "whatsapp": settings.WHATSAPP_PROVIDER,
        "ai": settings.AI_PROVIDER,
        "payments": settings.PAYMENT_PROVIDER,
        "storage": settings.STORAGE_PROVIDER,
    }
    ok = all(v.get("ok") for k, v in checks.items() if k != "providers")
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "degraded", "checks": checks})
