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


from apps.api.app.schemas.conversation import ConversationDetailRead, ConversationRead
import uuid


@router.get(
    "/conversations",
    response_model=list[ConversationRead],
    status_code=status.HTTP_200_OK,
    summary="List past conversations for current user",
)
async def list_conversations(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationRead]:
    service = ChatService(session)
    return await service.list_conversations(user_id=current_user.id, limit=limit, offset=offset)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Get conversation detail with messages and citations",
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> ConversationDetailRead:
    service = ChatService(session)
    return await service.get_conversation(conversation_id=conversation_id, user_id=current_user.id)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> None:
    service = ChatService(session)
    await service.delete_conversation(conversation_id=conversation_id, user_id=current_user.id)


from apps.api.app.models.audit import AuditLog
from apps.api.app.repositories.audit_repo import AuditLogRepository
from pydantic import BaseModel


class CitationClickRequest(BaseModel):
    chunk_id: str
    conversation_id: str | None = None
    document_title: str | None = None


@router.post(
    "/citations/click",
    status_code=status.HTTP_200_OK,
    summary="Track user click on a source citation link",
)
async def track_citation_click(
    payload: CitationClickRequest,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Records user interaction with a source citation.

    Measures 'Trust & Completeness': captures if users actually click
    the source links provided.
    """
    repo = AuditLogRepository(session)
    chunk_uuid = None
    try:
        chunk_uuid = uuid.UUID(payload.chunk_id)
    except (ValueError, TypeError):
        pass

    log_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        action="citation_click",
        resource_type="citation",
        resource_id=chunk_uuid,
        metadata_={
            "chunk_id": payload.chunk_id,
            "conversation_id": payload.conversation_id,
            "document_title": payload.document_title,
        },
    )
    await repo.create(log_entry)
    await session.commit()
    return {"status": "recorded", "chunk_id": payload.chunk_id}

