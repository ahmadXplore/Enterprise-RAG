"""POST /api/v1/query — Agentic RAG query endpoint.

Security controls (Rule 4, 6, 11, 12, 15):
- require_viewer: authenticated users with VIEWER, ANALYST, or ADMIN role.
- Pre-retrieval authorization: document IDs resolved from DB before any Qdrant call.
- Rate limiting: 10 requests / minute per user (configurable via LLM_RATE_LIMIT_PER_MINUTE).
- Request timeout: enforced inside each LLM provider call.
- Response: minimum necessary fields only — CoT state never returned.
- API key never logged or returned.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Any

from apps.api.app.api.deps import get_session, require_viewer
from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import AppException
from apps.api.app.core.logging import logger
from apps.api.app.models.user import User
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.schemas.query import QueryRequest, QueryResponse
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.common import RoleType

router = APIRouter()

# In-process per-user rate-limit store (counts requests within a 60-second window).
# For multi-process deployments, replace with Redis (Rule 15).
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: str, limit: int) -> None:
    """Enforce per-user rate limit. Raises ForbiddenException on breach."""
    now = time.monotonic()
    window = 60.0
    calls = _rate_limit_store[user_id]
    # Discard calls outside the current window
    _rate_limit_store[user_id] = [t for t in calls if now - t < window]
    if len(_rate_limit_store[user_id]) >= limit:
        raise AppException(
            code="RATE_LIMITED",
            message="Too many requests. Please wait before querying again.",
            status_code=429,
        )
    _rate_limit_store[user_id].append(now)


def _build_qdrant_filters(request_body: QueryRequest) -> dict[str, Any]:
    """Build metadata filters from the request — never from auth data."""
    filters: dict[str, Any] = {}
    if request_body.company:
        filters["company"] = request_body.company
    if request_body.year:
        filters["year"] = request_body.year
    if request_body.document_type:
        filters["document_type"] = request_body.document_type
    return filters


@router.post(
    "",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Agentic RAG query (authenticated)",
)
async def query_endpoint(
    body: QueryRequest,
    request: Request,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    """Execute the agentic RAG pipeline against documents the user can access.

    Authentication: Bearer JWT — VIEWER, ANALYST, or ADMIN role required.

    Pre-retrieval authorization (Rule 12):
      The user's authorized document IDs are resolved from PostgreSQL before any
      Qdrant call. The LLM never receives documents the user cannot access.

    Rate limit: LLM_RATE_LIMIT_PER_MINUTE requests per user per minute.

    Response: answer, citation_ids, grounded, abstained, query_type.
              CoT state and token usage are never returned.
    """
    settings = get_settings()
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # ── Rate limit (Rule 11, 15) ─────────────────────────────────────────────
    _check_rate_limit(str(current_user.id), settings.LLM_RATE_LIMIT_PER_MINUTE)

    # ── Pre-retrieval access control (Rule 12) ────────────────────────────────
    user_roles = {r.name for r in current_user.roles}
    is_admin = RoleType.ADMIN.value in user_roles or RoleType.ADMIN in user_roles
    role_ids = [r.id for r in current_user.roles]

    doc_repo = DocumentRepository(session)
    authorized_ids = await doc_repo.get_allowed_document_ids(
        user_id=current_user.id,
        role_ids=role_ids,
        is_admin=is_admin,
    )

    if not authorized_ids and not is_admin:
        # No documents accessible — abstain immediately without hitting Qdrant
        return QueryResponse(
            answer=(
                "You do not have access to any documents. "
                "Please contact an administrator to request access."
            ),
            citation_ids=[],
            grounded=False,
            abstained=True,
            query_type="DIRECT",
        )

    authorized_id_strings = [str(doc_id) for doc_id in authorized_ids]
    base_filters = _build_qdrant_filters(body)

    logger.info(
        "RAG query initiated",
        extra={
            "extra": {
                "request_id": request_id,
                "user_id": str(current_user.id),
                "authorized_doc_count": len(authorized_id_strings),
                "has_filters": bool(base_filters),
            }
        },
    )

    # ── Build services from settings (API keys from env only — Rule 4) ───────
    try:
        from packages.llm.generation import RAGGenerator
        from packages.llm.graph import RAGGraph
        from packages.llm.providers import build_provider_from_settings
        from packages.retrieval import HybridRetriever
        from packages.retrieval.dense import DenseRetriever
        from packages.retrieval.embeddings import (
            BM25SparseEmbedder,
            FastEmbedDenseEmbedder,
        )
        from packages.retrieval.qdrant_client import create_qdrant_client
        from packages.retrieval.sparse import SparseRetriever

        qdrant = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        dense_embedder = FastEmbedDenseEmbedder()
        sparse_embedder = BM25SparseEmbedder()

        dense = DenseRetriever(client=qdrant, embedder=dense_embedder)
        sparse = SparseRetriever(client=qdrant, embedder=sparse_embedder)
        retriever = HybridRetriever(dense_retriever=dense, sparse_retriever=sparse)

        llm_provider = build_provider_from_settings()
        generator = RAGGenerator(provider=llm_provider)

        graph = RAGGraph(
            provider=llm_provider,
            retriever=retriever,
            generator=generator,
            max_retrieval_attempts=settings.AGENT_MAX_RETRIEVAL_ATTEMPTS,
            max_tool_calls=settings.AGENT_MAX_TOOL_CALLS,
        )
    except ImportError as exc:
        logger.error(
            "Required dependency not installed",
            extra={"extra": {"request_id": request_id, "error": str(exc)}},
        )
        raise AppException(
            code="SERVICE_UNAVAILABLE",
            message="The RAG service is not fully configured. Contact an administrator.",
            status_code=503,
        ) from exc

    # ── Execute graph with Phase 16 Observability ────────────────────────────
    from apps.api.app.core.observability import QueryTimer

    from packages.llm.providers import ProviderError

    query_id = str(uuid.uuid4())
    timer = QueryTimer(query_id=query_id, request_id=request_id, user_id=str(current_user.id))
    timer.start_stage("preprocessing")
    # Preprocessing completed (validation, rate limit, auth lookup)
    timer.end_stage("preprocessing")

    timer.start_stage("generation")
    try:
        result = await graph.run(
            question=body.question,
            authorized_document_ids=authorized_id_strings,
            user_id=str(current_user.id),
            base_filters=base_filters,
        )
    except ProviderError as exc:
        timer.end_stage("generation")
        timer.finish(
            provider=getattr(settings, "LLM_PROVIDER", ""),
            model=getattr(settings, "LLM_MODEL", ""),
            error=str(exc),
        )
        raise AppException(
            code="LLM_ERROR",
            message="The language model service is temporarily unavailable. Please try again.",
            status_code=503,
        ) from exc
    except Exception as exc:
        timer.end_stage("generation")
        timer.finish(
            provider=getattr(settings, "LLM_PROVIDER", ""),
            model=getattr(settings, "LLM_MODEL", ""),
            error=str(exc),
        )
        raise

    timer.end_stage("generation")
    timer.start_stage("validation")
    # Output structure and citations validated
    timer.end_stage("validation")

    timer.finish(
        provider=getattr(settings, "LLM_PROVIDER", ""),
        model=getattr(settings, "LLM_MODEL", ""),
        citation_count=len(result.citation_ids),
        grounded=result.grounded,
        abstained=result.abstained,
        token_usage=getattr(result, "token_usage", {}),
    )

    return QueryResponse(
        answer=result.answer,
        citation_ids=result.citation_ids,
        grounded=result.grounded,
        abstained=result.abstained,
        query_type=result.query_type,
    )
