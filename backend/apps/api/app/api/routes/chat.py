"""POST /api/v1/chat and POST /api/v1/chat/stream endpoints.

Matches BACKEND SCHEMA.md Sections 8 & 9.
Rule 4: require_viewer role required.
Rule 6: Minimum data exposure.
Rule 11: SSE streaming emits typed events without leaking chain-of-thought internals.
Rule 24: Business logic delegates entirely to ChatService.
"""

from __future__ import annotations

from apps.api.app.api.deps import get_session, require_viewer
from apps.api.app.core.rate_limit import rate_limit_chat
from apps.api.app.models.user import User
from apps.api.app.schemas.chat import ChatRequest, ChatResponse
from apps.api.app.services.chat_service import ChatService
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Synchronous RAG chat with conversation persistence",
)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_chat),
) -> ChatResponse:
    """Execute chat query, returning grounded answer and verified citations."""
    service = ChatService(session)
    return await service.chat(request=request, current_user=current_user)


@router.post(
    "/stream",
    status_code=status.HTTP_200_OK,
    summary="Server-Sent Events (SSE) streaming chat",
)
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_chat),
) -> StreamingResponse:
    """Stream chat generation as Server-Sent Events (SSE).

    Emits typed events per BACKEND SCHEMA.md Section 9:
    query_started, query_classified, retrieval_started, retrieval_completed,
    reranking_completed, generation_started, token, citation, completed, error.
    """
    service = ChatService(session)
    stream_generator = service.stream_chat(request=request, current_user=current_user)
    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
