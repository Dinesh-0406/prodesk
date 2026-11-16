"""Redis fixed-window rate limiting.

Fails *open* on Redis outage for general endpoints (availability) but callers protecting
credentials (login/OTP) pass ``fail_closed=True``.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import redis
from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimited
from app.core.logging import get_logger
from app.core.redis import get_redis

log = get_logger(__name__)


def hit(key: str, limit: int, window_seconds: int, *, fail_closed: bool = False) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    bucket = int(time.time() // window_seconds)
    rkey = f"rl:{key}:{bucket}"
    try:
        r = get_redis()
        pipe = r.pipeline()
        pipe.incr(rkey)
        pipe.expire(rkey, window_seconds + 1)
        count, _ = pipe.execute()
    except redis.RedisError:
        log.warning("rate_limit_backend_unavailable", extra={"key": key.split(":")[0]})
        if fail_closed:
            raise RateLimited("Service temporarily unavailable, please retry") from None
        return
    if int(count) > limit:
        raise RateLimited("Too many requests, please slow down", details={"retry_after_seconds": window_seconds})


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def limiter(name: str, limit: int, window_seconds: int, *, fail_closed: bool = False) -> Callable[[Request], None]:
    """FastAPI dependency factory limiting per client IP."""

    def _dep(request: Request) -> None:
        hit(f"{name}:{client_ip(request)}", limit, window_seconds, fail_closed=fail_closed)

    return _dep
