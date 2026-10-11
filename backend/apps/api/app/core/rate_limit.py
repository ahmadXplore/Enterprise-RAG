"""Redis-backed sliding-window rate limiter (Risk 2 mitigation).

Replaces the per-process in-memory approach with a shared Redis counter so that
rate limits are enforced correctly across all workers/pods in a horizontally
scaled deployment.

Algorithm: sliding-window log using Redis ZADD / ZREMRANGEBYSCORE / ZCARD.

Fail-open behaviour: if Redis is unreachable the limiter logs a warning and
allows the request through so that a Redis outage does not take down the API.

Usage::

    # In a route that needs rate-limiting:
    from apps.api.app.core.rate_limit import RateLimitDep, build_rate_limit_dep
    rate_limit_login = build_rate_limit_dep(max_requests=5, window_seconds=60)

    @router.post("/login")
    async def login(..., _rl: None = Depends(rate_limit_login)):
        ...
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response, status

logger = logging.getLogger("enterprise_rag")

# ---------------------------------------------------------------------------
# Shared Redis connection pool
# ---------------------------------------------------------------------------
_redis_pool: object | None = None  # redis.asyncio.Redis instance, set at startup


def set_redis_pool(pool: object) -> None:  # noqa: ANN001
    """Register the shared Redis connection pool.  Called from ``lifespan``."""
    global _redis_pool  # noqa: PLW0603
    _redis_pool = pool


def get_redis_pool() -> object | None:
    """Return the shared pool (may be None if Redis is not configured)."""
    return _redis_pool


# ---------------------------------------------------------------------------
# Core sliding-window counter
# ---------------------------------------------------------------------------
async def _sliding_window_check(
    key: str,
    max_requests: int,
    window_seconds: int,
) -> tuple[bool, int, int]:
    """Check and increment a Redis sliding-window counter.

    Returns:
        (allowed, remaining, retry_after_seconds)
    """
    pool = get_redis_pool()
    if pool is None:
        # No Redis — fail-open
        return True, max_requests, 0

    now = time.time()
    window_start = now - window_seconds

    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        r: aioredis.Redis = pool  # type: ignore[assignment]
        pipe = r.pipeline()
        # Remove entries older than the window
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Add this request with current timestamp as score and member
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Expire the key after the window so Redis doesn't accumulate stale keys
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()
        current_count: int = results[2]
    except Exception as exc:
        logger.warning(
            "Rate limiter Redis error — failing open",
            extra={"extra": {"error": str(exc)}},
        )
        return True, max_requests, 0

    if current_count > max_requests:
        remaining = 0
        return False, remaining, window_seconds
    return True, max(0, max_requests - current_count), 0


# ---------------------------------------------------------------------------
# FastAPI dependency factory
# ---------------------------------------------------------------------------
def build_rate_limit_dep(
    max_requests: int = 10,
    window_seconds: int = 60,
) -> Callable:
    """Return a FastAPI dependency that enforces a sliding-window rate limit.

    The limit key is ``ratelimit:{path}:{client_ip}``.
    On breach: raises HTTP 429 and sets ``Retry-After``, ``X-RateLimit-*`` headers.
    On Redis failure: logs and allows the request (fail-open).

    Args:
        max_requests: Maximum requests allowed in *window_seconds*.
        window_seconds: Length of the sliding window in seconds.
    """

    async def _rate_limit_dep(request: Request, response: Response) -> None:
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or (request.client.host if request.client else "unknown")
        )
        key = f"ratelimit:{request.url.path}:{client_ip}"
        allowed, remaining, retry_after = await _sliding_window_check(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        # Always set informational headers (Rule 3 — transparency)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        if retry_after:
            response.headers["Retry-After"] = str(retry_after)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

    return _rate_limit_dep


# ---------------------------------------------------------------------------
# Pre-built dependencies for commonly rate-limited endpoints
# ---------------------------------------------------------------------------
# Login: 5 attempts per 60-second window per IP (brute-force protection)
rate_limit_login = build_rate_limit_dep(max_requests=5, window_seconds=60)

# Chat: 10 requests per 60-second window per IP (cost-DOS prevention, Rule 15)
rate_limit_chat = build_rate_limit_dep(max_requests=10, window_seconds=60)

# Search: 30 requests per 60-second window per IP (Rule 11, 15)
rate_limit_search = build_rate_limit_dep(max_requests=30, window_seconds=60)

# Ingestion / Registration: 10 requests per 60-second window per IP (Rule 11, 15)
rate_limit_ingest = build_rate_limit_dep(max_requests=10, window_seconds=60)

# General Write / Mutations: 20 requests per 60-second window per IP (Rule 11, 15)
rate_limit_write = build_rate_limit_dep(max_requests=20, window_seconds=60)
