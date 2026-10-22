"""Typed state for the LangGraph agentic RAG pipeline (Phase 11).

All fields are plain Python types — no database models, no ORM objects.
Chain-of-thought fields (classification reasoning, constraint extraction, evidence
assessment) are explicitly marked and MUST NOT be serialised into any API response.
"""

from __future__ import annotations

from typing import Any, TypedDict

from packages.llm.generation import GenerationResult
from packages.retrieval.models import RetrievalResult


class GraphState(TypedDict, total=False):
    # ── Input (set once, never mutated) ──────────────────────────────────────
    question: str
    conversation_history: list[dict[str, str]]  # list of {role, content}
    contextualized_question: str | None  # resolved standalone question after multi-turn coreference
    authorized_document_ids: list[str]  # pre-resolved, never from user input
    authorized_documents: list[dict[str, str]]  # list of {id, title, organization}
    user_id: str  # for audit / logging only
    base_filters: dict[str, Any]  # company/year/type filters from request

    # ── Classification (CoT — never returned to client) ──────────────────────
    query_type: str  # DIRECT | NUMERICAL | TEMPORAL | COMPARISON | …
    requires_calculation: bool

    # ── Constraint extraction (CoT — never returned to client) ───────────────
    entities: list[str]
    metric: str | None
    time_period: int | None
    retrieval_filters: dict[str, Any]

    # ── Retrieval state ───────────────────────────────────────────────────────
    retrieval_query: str  # may differ from question after expansion
    evidence: list[RetrievalResult]
    retrieval_attempts: int  # loop counter, enforces max_retrieval_attempts
    tool_calls: int  # total node invocations, enforces max_tool_calls

    # ── Evidence assessment (CoT — never returned to client) ─────────────────
    evidence_sufficient: bool

    # ── Result ────────────────────────────────────────────────────────────────
    result: GenerationResult | None

    # ── Error ─────────────────────────────────────────────────────────────────
    error: str | None
