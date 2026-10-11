"""Chat service managing conversations, messages, generation, and SSE streaming.

Matches BACKEND SCHEMA.md Sections 8 & 9.
Rule 4, 6: Conversation ownership verified, pre-retrieval authorization enforced.
Rule 11: Chain-of-thought internal reasoning is never streamed or returned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import AsyncIterator
from typing import Any

from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import ForbiddenException, NotFoundException
from apps.api.app.models.conversation import Conversation, Message, MessageCitation
from apps.api.app.models.user import User
from apps.api.app.repositories.conversation_repo import ConversationRepository
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.schemas.chat import ChatCitationItem, ChatRequest, ChatResponse
from sqlalchemy.ext.asyncio import AsyncSession

from packages.llm.generation import GenerationResult
from packages.llm.graph import RAGGraph
from packages.schemas.common import RoleType

logger = logging.getLogger("enterprise_rag")

# ---------------------------------------------------------------------------
# Risk 3 mitigation: per-user SSE connection cap
# A module-level counter prevents one user from exhausting server file
# descriptors by opening many concurrent SSE streams.
# ---------------------------------------------------------------------------
_sse_lock = threading.Lock()
_sse_active: dict[str, int] = {}  # user_id -> active stream count


def _sse_acquire(user_id: str, max_streams: int) -> bool:
    """Increment the SSE counter for *user_id*.  Returns False if cap exceeded."""
    with _sse_lock:
        current = _sse_active.get(user_id, 0)
        if current >= max_streams:
            return False
        _sse_active[user_id] = current + 1
        return True


def _sse_release(user_id: str) -> None:
    """Decrement the SSE counter for *user_id*."""
    with _sse_lock:
        current = _sse_active.get(user_id, 0)
        _sse_active[user_id] = max(0, current - 1)


class ChatService:
    """Manages chat conversations, message persistence, and streaming execution."""

    def __init__(
        self,
        session: AsyncSession,
        graph: RAGGraph | None = None,
    ) -> None:
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.doc_repo = DocumentRepository(session)
        self._graph = graph

    def _get_graph(self) -> RAGGraph:
        """Resolve or lazily construct the agentic RAGGraph."""
        if self._graph is not None:
            return self._graph

        settings = get_settings()
        from packages.llm.generation import RAGGenerator
        from packages.llm.providers import build_provider_from_settings
        from packages.retrieval.dense import DenseRetriever
        from packages.retrieval.hybrid import HybridRetriever
        from packages.retrieval.qdrant_client import create_qdrant_client
        from packages.retrieval.sparse import SparseRetriever

        provider = build_provider_from_settings()
        client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        try:
            from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder

            dense_emb = FastEmbedDenseEmbedder()
            sparse_emb = BM25SparseEmbedder()
        except Exception:
            from packages.retrieval.embeddings import DeterministicMockEmbedder

            dense_emb = DeterministicMockEmbedder()
            sparse_emb = dense_emb

        try:
            from packages.retrieval.reranker import FastEmbedReranker

            reranker = FastEmbedReranker()
        except Exception:
            from packages.retrieval.reranker import LexicalSemanticMockReranker

            reranker = LexicalSemanticMockReranker()

        dense = DenseRetriever(client=client, embedder=dense_emb)
        sparse = SparseRetriever(client=client, embedder=sparse_emb)
        retriever = HybridRetriever(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=reranker,
        )
        generator = RAGGenerator(provider=provider)

        self._graph = RAGGraph(
            provider=provider,
            retriever=retriever,
            generator=generator,
            max_retrieval_attempts=settings.AGENT_MAX_RETRIEVAL_ATTEMPTS,
            max_tool_calls=settings.AGENT_MAX_TOOL_CALLS,
        )
        return self._graph

    async def _resolve_conversation(
        self,
        conversation_id: uuid.UUID | None,
        user: User,
        initial_title: str,
    ) -> Conversation:
        """Get existing conversation verifying ownership, or create a new one."""
        if conversation_id is not None:
            conv = await self.conv_repo.get_by_id(conversation_id)
            if conv is None:
                raise NotFoundException(f"Conversation {conversation_id} not found")
            if conv.user_id != user.id:
                raise ForbiddenException("Access to this conversation is denied")
            return conv

        # Create new conversation
        title = initial_title[:40] if initial_title else "New Conversation"
        new_conv = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            title=title,
        )
        created = await self.conv_repo.create(new_conv)
        return created

    async def _resolve_authorized_docs(self, user: User) -> list[str]:
        """Resolve authorized document IDs for pre-retrieval access control."""
        is_admin = any(
            r.name == RoleType.ADMIN.value or r.name == RoleType.ADMIN for r in user.roles
        )
        role_ids = [r.id for r in user.roles]
        allowed_uuids = await self.doc_repo.get_allowed_document_ids(
            user_id=user.id,
            role_ids=role_ids,
            is_admin=is_admin,
        )
        return [str(u) for u in allowed_uuids]

    async def chat(
        self,
        request: ChatRequest,
        current_user: User,
    ) -> ChatResponse:
        """Execute synchronous chat interaction with DB persistence."""
        conv = await self._resolve_conversation(
            request.conversation_id, current_user, request.message
        )
        authorized_doc_ids = await self._resolve_authorized_docs(current_user)

        # Record user message in DB
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content=request.message,
        )
        self.session.add(user_msg)

        # Run pipeline with Phase 16 observability
        from apps.api.app.core.observability import QueryTimer
        query_id = str(uuid.uuid4())
        timer = QueryTimer(query_id=query_id, request_id=query_id, user_id=str(current_user.id))
        timer.start_stage("preprocessing")
        timer.end_stage("preprocessing")

        timer.start_stage("generation")
        graph = self._get_graph()
        gen_result: GenerationResult = await graph.run(
            question=request.message,
            authorized_document_ids=authorized_doc_ids,
            user_id=str(current_user.id),
            base_filters=request.filters or {},
        )
        timer.end_stage("generation")
        timer.finish(
            citation_count=len(gen_result.citation_ids),
            grounded=gen_result.grounded,
            abstained=gen_result.abstained,
            token_usage=getattr(gen_result, "token_usage", {}),
        )

        # Record assistant message in DB
        assistant_msg_id = uuid.uuid4()
        asst_msg = Message(
            id=assistant_msg_id,
            conversation_id=conv.id,
            role="assistant",
            content=gen_result.answer,
            query_type=gen_result.query_type,
            grounded=gen_result.grounded,
            abstained=gen_result.abstained,
        )
        self.session.add(asst_msg)

        # Persist citations if chunk IDs are valid UUIDs
        citations: list[ChatCitationItem] = []
        for cid in dict.fromkeys(gen_result.citation_ids):
            chunk_uuid = None
            try:
                chunk_uuid = uuid.UUID(cid)
            except (ValueError, TypeError):
                chunk_uuid = None

            if chunk_uuid:
                cit_record = MessageCitation(
                    id=uuid.uuid4(),
                    message_id=assistant_msg_id,
                    chunk_id=chunk_uuid,
                    citation_label=cid,
                )
                self.session.add(cit_record)

            citations.append(ChatCitationItem(chunk_id=cid))

        await self.session.commit()

        return ChatResponse(
            message_id=str(assistant_msg_id),
            conversation_id=str(conv.id),
            answer=gen_result.answer,
            grounded=gen_result.grounded,
            abstained=gen_result.abstained,
            citations=citations,
        )

    async def stream_chat(
        self,
        request: ChatRequest,
        current_user: User,
    ) -> AsyncIterator[str]:
        """Server-Sent Events (SSE) streaming chat pipeline.

        Risk 3 mitigations applied:
        - Per-user concurrent stream cap (SSE_MAX_CONCURRENT_STREAMS_PER_USER).
        - asyncio.timeout(LLM_TIMEOUT_SECONDS) around the entire pipeline so
          a slow or hanging LLM cannot hold the connection open indefinitely.

        Emits events in sequence matching BACKEND SCHEMA.md Section 9:
        query_started -> query_classified -> retrieval_started ->
        retrieval_completed -> reranking_completed -> generation_started ->
        token -> citation -> completed
        """

        def _sse_event(event_name: str, data: dict[str, Any]) -> str:
            return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"

        settings = get_settings()
        user_id_str = str(current_user.id)
        query_id = str(uuid.uuid4())

        yield _sse_event("query_started", {"query_id": query_id, "status": "started"})

        # Risk 3: enforce per-user concurrent stream cap
        max_streams = settings.SSE_MAX_CONCURRENT_STREAMS_PER_USER
        if not _sse_acquire(user_id_str, max_streams):
            logger.warning(
                "SSE stream rejected — per-user cap exceeded",
                extra={"extra": {"user_id": user_id_str, "max_streams": max_streams}},
            )
            yield _sse_event("error", {"detail": "too_many_streams"})
            return

        try:
            conv = await self._resolve_conversation(
                request.conversation_id, current_user, request.message
            )
            authorized_doc_ids = await self._resolve_authorized_docs(current_user)

            # Record user message in DB
            user_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="user",
                content=request.message,
            )
            self.session.add(user_msg)

            # Immediate initial step notice so user sees activity instantaneously
            yield _sse_event(
                "agent_step",
                {
                    "step": "classify_query",
                    "title": "Analyzing query intent",
                    "detail": "Examining question scope & research requirements...",
                    "status": "in_progress",
                },
            )

            # Risk 3: timeout guard — prevents indefinitely held connections.
            timeout_secs = settings.LLM_TIMEOUT_SECONDS
            gen_result = None
            try:
                async with asyncio.timeout(timeout_secs):
                    graph = self._get_graph()
                    async for item in graph.astream_run(
                        question=request.message,
                        authorized_document_ids=authorized_doc_ids,
                        user_id=user_id_str,
                        base_filters=request.filters or {},
                    ):
                        if item.get("type") == "step":
                            yield _sse_event(
                                "agent_step",
                                {
                                    "step": item.get("node", "step"),
                                    "title": item.get("title", ""),
                                    "detail": item.get("detail", ""),
                                    "status": item.get("status", "completed"),
                                },
                            )
                        elif item.get("type") == "result":
                            gen_result = item.get("result")
            except TimeoutError:
                logger.warning(
                    "SSE generation timed out",
                    extra={"extra": {"query_id": query_id, "timeout_secs": timeout_secs}},
                )
                yield _sse_event("error", {"detail": "generation_timeout"})
                return

            if gen_result is None:
                gen_result = GenerationResult(
                    answer="I was unable to find sufficient evidence to answer this question.",
                    citation_ids=[],
                    grounded=False,
                    abstained=True,
                    query_type="DIRECT",
                )

            yield _sse_event(
                "retrieval_completed", {"citations_count": len(gen_result.citation_ids)}
            )
            yield _sse_event("reranking_completed", {"status": "completed"})
            yield _sse_event("generation_started", {"status": "generating"})

            # Stream answer in progressive tokens with smooth pacing
            answer = gen_result.answer
            words = answer.split(" ")
            chunk_size = 3
            for i in range(0, len(words), chunk_size):
                token_chunk = " ".join(words[i : i + chunk_size]) + " "
                yield _sse_event("token", {"token": token_chunk})
                await asyncio.sleep(0.015)

            # Record assistant message in DB
            assistant_msg_id = uuid.uuid4()
            asst_msg = Message(
                id=assistant_msg_id,
                conversation_id=conv.id,
                role="assistant",
                content=answer,
                query_type=gen_result.query_type,
                grounded=gen_result.grounded,
                abstained=gen_result.abstained,
            )
            self.session.add(asst_msg)

            # Persist and yield citations
            citations: list[ChatCitationItem] = []
            for cid in dict.fromkeys(gen_result.citation_ids):
                chunk_uuid = None
                try:
                    chunk_uuid = uuid.UUID(cid)
                except (ValueError, TypeError):
                    chunk_uuid = None

                if chunk_uuid:
                    cit_record = MessageCitation(
                        id=uuid.uuid4(),
                        message_id=assistant_msg_id,
                        chunk_id=chunk_uuid,
                        citation_label=cid,
                    )
                    self.session.add(cit_record)

                citations.append(ChatCitationItem(chunk_id=cid))
                yield _sse_event("citation", {"citation_id": cid, "chunk_id": cid})

            await self.session.commit()

            yield _sse_event(
                "completed",
                {
                    "message_id": str(assistant_msg_id),
                    "conversation_id": str(conv.id),
                    "grounded": gen_result.grounded,
                    "abstained": gen_result.abstained,
                    "citations": [c.model_dump() for c in citations],
                },
            )
        except Exception as exc:
            logger.error(
                "SSE stream failed",
                extra={"extra": {"query_id": query_id, "error": str(exc)}},
            )
            yield _sse_event("error", {"message": "An error occurred during generation."})
        finally:
            # Always release the slot so the cap doesn't permanently block the user.
            _sse_release(user_id_str)
