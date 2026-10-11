"""Health check routes: GET /health, /health/db, /health/qdrant, /health/redis, /health/llm.

Matches BACKEND SCHEMA.md Section 19.
Rule 4 & 6: No auth required, but strictly never expose credentials, urls, or stack traces.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx
from apps.api.app.config import get_settings
from apps.api.app.core.database import check_db_health
from apps.api.app.schemas.health import (
    CorpusStatsResponse,
    DatabaseHealthResponse,
    HealthResponse,
    LLMHealthResponse,
    QdrantHealthResponse,
    RedisHealthResponse,
)
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="System liveness check")
async def health() -> HealthResponse:
    """Returns service liveness. No auth required."""
    return HealthResponse(
        status="ok",
        service="enterprise-rag-api",
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/db",
    response_model=DatabaseHealthResponse,
    summary="Database connectivity check",
)
async def health_db() -> DatabaseHealthResponse:
    """Verifies the database is reachable by executing SELECT 1."""
    start = time.monotonic()
    connected = await check_db_health()
    latency_ms = round((time.monotonic() - start) * 1000, 2)

    return DatabaseHealthResponse(
        status="ok" if connected else "degraded",
        database="postgresql",
        connected=connected,
        latency_ms=latency_ms,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/qdrant",
    response_model=QdrantHealthResponse,
    summary="Qdrant vector store connectivity check",
)
async def health_qdrant() -> QdrantHealthResponse:
    """Verifies Qdrant vector store connectivity safely."""
    settings = get_settings()
    start = time.monotonic()
    connected = False

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            headers = {}
            if settings.QDRANT_API_KEY:
                headers["api-key"] = settings.QDRANT_API_KEY
            resp = await client.get(f"{settings.QDRANT_URL}/healthz", headers=headers)
            connected = resp.status_code == 200
    except Exception:
        connected = False

    latency_ms = round((time.monotonic() - start) * 1000, 2)
    return QdrantHealthResponse(
        status="ok" if connected else "degraded",
        service="qdrant",
        connected=connected,
        latency_ms=latency_ms,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/redis",
    response_model=RedisHealthResponse,
    summary="Redis cache connectivity check",
)
async def health_redis() -> RedisHealthResponse:
    """Verifies Redis cache connectivity safely."""
    settings = get_settings()
    start = time.monotonic()
    connected = False

    try:
        import urllib.parse

        parsed = urllib.parse.urlparse(settings.REDIS_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        import asyncio

        reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=1.0)
        writer.write(b"PING\r\n")
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=1.0)
        writer.close()
        await writer.wait_closed()
        connected = b"+PONG" in line
    except Exception:
        connected = False

    latency_ms = round((time.monotonic() - start) * 1000, 2)
    return RedisHealthResponse(
        status="ok" if connected else "degraded",
        service="redis",
        connected=connected,
        latency_ms=latency_ms,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/stats",
    response_model=CorpusStatsResponse,
    summary="Aggregated corpus statistics for the dashboard",
)
async def health_stats() -> CorpusStatsResponse:
    """Returns real document, chunk, and query counts from the database."""
    from apps.api.app.core.database import AsyncSessionLocal
    from sqlalchemy import text

    total_docs = 0
    ready_docs = 0
    total_chunks = 0
    total_queries = 0

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM documents"))
            total_docs = result.scalar() or 0

            result = await session.execute(
                text("SELECT COUNT(*) FROM documents WHERE status = 'ready'")
            )
            ready_docs = result.scalar() or 0

            result = await session.execute(text("SELECT COUNT(*) FROM document_chunks"))
            total_chunks = result.scalar() or 0

            result = await session.execute(text("SELECT COUNT(*) FROM queries"))
            total_queries = result.scalar() or 0
    except Exception:
        pass

    return CorpusStatsResponse(
        total_documents=total_docs,
        ready_documents=ready_docs,
        total_chunks=total_chunks,
        total_queries=total_queries,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/health/llm",
    response_model=LLMHealthResponse,
    summary="LLM provider configuration and readiness check",
)
async def health_llm() -> LLMHealthResponse:
    """Verifies LLM provider configuration safely without making paid API calls."""
    settings = get_settings()
    configured = False

    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        configured = True
    elif settings.LLM_PROVIDER == "openrouter" and settings.OPENROUTER_API_KEY:
        configured = True
    elif settings.LLM_PROVIDER == "ollama" and settings.OLLAMA_BASE_URL:
        configured = True

    return LLMHealthResponse(
        status="ok" if configured else "degraded",
        service="llm",
        provider=settings.LLM_PROVIDER,
        configured=configured,
        timestamp=datetime.now(UTC),
    )
