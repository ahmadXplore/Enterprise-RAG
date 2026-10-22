"""FastAPI application factory for Enterprise RAG API."""

import uuid
from contextlib import asynccontextmanager

from apps.api.app.api.routes.admin import router as admin_router
from apps.api.app.api.routes.auth import router as auth_router
from apps.api.app.api.routes.chat import router as chat_router
from apps.api.app.api.routes.documents import router as documents_router
from apps.api.app.api.routes.evaluations import router as evaluations_router
from apps.api.app.api.routes.health import router as health_router
from apps.api.app.api.routes.ingestion import router as ingestion_router
from apps.api.app.api.routes.query import router as query_router
from apps.api.app.api.routes.search import router as search_router
from apps.api.app.api.routes.users import router as users_router
from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import (
    AppException,
    app_exception_handler,
    database_exception_handler,
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from apps.api.app.core.logging import logger, setup_logging
from apps.api.app.core.rate_limit import set_redis_pool
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

settings = get_settings()
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Enterprise RAG API starting up")

    # Risk 2 mitigation: initialise shared Redis pool for distributed rate limiting.
    redis_client = None
    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
        set_redis_pool(redis_client)
        logger.info(
            "Redis rate-limit pool initialised",
            extra={"extra": {"url": settings.REDIS_URL}},
        )
    except Exception as exc:
        logger.warning(
            "Redis unavailable — rate limiting will fail-open",
            extra={"extra": {"error": str(exc)}},
        )

    yield

    if redis_client is not None:
        await redis_client.aclose()
        logger.info("Redis rate-limit pool closed")

    logger.info("Enterprise RAG API shutting down")


app = FastAPI(
    title="Enterprise RAG API",
    description="Document Intelligence & Agentic RAG Platform",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
    lifespan=lifespan,
)

# CORS — explicit allowlist; never use wildcard in production (Rule 7, Rule 4)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Enforce production security headers (Rule 4, Rule 7)."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'; object-src 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Inject a unique request ID for log correlation."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Exception handlers — safe, no stack traces exposed to clients (Rule 14)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(documents_router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(ingestion_router, prefix="/api/v1/ingestion", tags=["ingestion"])
app.include_router(search_router, prefix="/api/v1/search", tags=["search"])
app.include_router(chat_router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(query_router, prefix="/api/v1/query", tags=["query"])
app.include_router(evaluations_router, prefix="/api/v1/evaluations", tags=["evaluations"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])

