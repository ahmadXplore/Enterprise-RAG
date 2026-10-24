"""POST /api/v1/chat and POST /api/v1/chat/stream endpoints.

Matches BACKEND SCHEMA.md Sections 8 & 9.
Rule 4: require_viewer role required.
Rule 6: Minimum data exposure.
Rule 11: SSE streaming emits typed events without leaking chain-of-thought internals.
Rule 24: Business logic delegates entirely to ChatService.
"""

from __future__ import annotations

from typing import Any

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


class ChatFeedbackRequest(BaseModel):
    message_id: str
    conversation_id: str | None = None
    rating: str  # "thumbs_up" | "thumbs_down"
    feedback_text: str | None = None  # user input in correction UI: "What was missing or incorrect?"
    tags: list[str] | None = None  # e.g., ["Missing facts", "Incorrect calculations", "Outdated data"]
    user_query: str | None = None


@router.post(
    "/feedback",
    status_code=status.HTTP_200_OK,
    summary="Submit binary +/- feedback and correction details on an assistant response",
)
async def submit_chat_feedback(
    payload: ChatFeedbackRequest,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Records binary (+/-) feedback and inline corrections from real users.

    Captures completeness and accuracy signals directly from users to pinpoint
    vector database and knowledge gaps.
    """
    msg_uuid = None
    try:
        msg_uuid = uuid.UUID(payload.message_id)
    except (ValueError, TypeError):
        pass

    log_entry = AuditLog(
        id=uuid.uuid4(),
        user_id=current_user.id,
        action="user_feedback",
        resource_type="message",
        resource_id=msg_uuid,
        metadata_={
            "message_id": payload.message_id,
            "conversation_id": payload.conversation_id,
            "rating": payload.rating,
            "score": 1 if payload.rating == "thumbs_up" else -1,
            "feedback_text": payload.feedback_text.strip() if payload.feedback_text else None,
            "tags": payload.tags or [],
            "user_query": payload.user_query,
        },
    )
    session.add(log_entry)
    await session.commit()

    return {
        "status": "success",
        "feedback_id": str(log_entry.id),
        "message_id": payload.message_id,
        "rating": payload.rating,
    }


from sqlalchemy import select


@router.get(
    "/feedback/{message_id}",
    status_code=status.HTTP_200_OK,
    summary="Get recorded user feedback for a message",
)
async def get_message_feedback(
    message_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve existing feedback given by current user for a message."""
    msg_uuid = None
    try:
        msg_uuid = uuid.UUID(message_id)
    except (ValueError, TypeError):
        pass

    query = (
        select(AuditLog)
        .where(
            AuditLog.user_id == current_user.id,
            AuditLog.action == "user_feedback",
        )
        .order_by(AuditLog.created_at.desc())
    )
    res = await session.execute(query)
    logs = res.scalars().all()

    for l in logs:
        meta = l.metadata_ or {}
        if meta.get("message_id") == message_id or (msg_uuid and l.resource_id == msg_uuid):
            return {
                "message_id": message_id,
                "rating": meta.get("rating"),
                "feedback_text": meta.get("feedback_text"),
                "tags": meta.get("tags", []),
                "created_at": l.created_at.isoformat(),
            }

    return {"message_id": message_id, "rating": None, "feedback_text": None, "tags": []}


@router.get(
    "/conversations/{conversation_id}/feedback",
    status_code=status.HTTP_200_OK,
    summary="Get all recorded user feedback for a conversation",
)
async def get_conversation_feedback(
    conversation_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Retrieve feedback mapping { message_id: feedback_data } for a conversation."""
    query = (
        select(AuditLog)
        .where(
            AuditLog.user_id == current_user.id,
            AuditLog.action == "user_feedback",
        )
        .order_by(AuditLog.created_at.asc())
    )
    res = await session.execute(query)
    logs = res.scalars().all()

    feedback_map: dict[str, Any] = {}
    for l in logs:
        meta = l.metadata_ or {}
        if meta.get("conversation_id") == conversation_id:
            m_id = meta.get("message_id") or (str(l.resource_id) if l.resource_id else None)
            if m_id:
                feedback_map[m_id] = {
                    "rating": meta.get("rating"),
                    "feedback_text": meta.get("feedback_text"),
                    "tags": meta.get("tags", []),
                    "created_at": l.created_at.isoformat(),
                }

    return {"conversation_id": conversation_id, "feedback": feedback_map}
