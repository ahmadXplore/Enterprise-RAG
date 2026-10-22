"""LangGraph agentic RAG pipeline (Phase 11).

Graph topology (matches build prompt exactly):
  START
    ↓
  classify_query
    ↓
  extract_constraints
    ↓
  apply_access_filter        (injects authorized_document_ids into retrieval_filters)
    ↓
  retrieve
    ↓
  assess_evidence
    ├─ insufficient + attempts < max → expand_query → retrieve  (loop, max 2 extra)
    ├─ numerical                    → calculate
    ├─ comparison                   → retrieve_comparison
    └─ sufficient / max-reached     → generate
    ↓
  validate_citations
    ↓
  finalize
    ↓
  END

Security / stop-condition rules (Rule 11, 15):
  - max_retrieval_attempts: configurable (default 3 total).
  - max_tool_calls:         configurable (default 10 total).
  - Abstains when evidence remains insufficient after all attempts.
  - CoT state (classification, constraints, evidence assessment) is never returned
    to callers — only `result` from finalize() is exposed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from packages.llm.generation import GenerationResult, RAGGenerator, validate_citations
from packages.llm.graph_state import GraphState
from packages.llm.prompt import (
    build_constraint_extraction_messages,
    build_contextualize_query_messages,
    build_expansion_messages,
    build_query_classification_messages,
)
from packages.llm.providers import ProviderError, parse_json_content
from packages.llm.workflows import ComparisonWorkflow, NumericalWorkflow, TemporalWorkflow
from packages.retrieval.models import RetrievalResult

logger = logging.getLogger("enterprise_rag")

ALIAS_MAP: dict[str, str] = {
    "stanford": "Stanford University",
    "stanford university": "Stanford University",
    "harvard": "Harvard University",
    "harvard university": "Harvard University",
    "mit": "MIT",
    "mit eecs": "MIT EECS",
    "cmu": "Carnegie Mellon University",
    "carnegie mellon": "Carnegie Mellon University",
    "carnegie mellon university": "Carnegie Mellon University",
    "berkeley": "UC Berkeley",
    "uc berkeley": "UC Berkeley",
    "oxford": "University of Oxford",
    "university of oxford": "University of Oxford",
    "cambridge": "University of Cambridge",
    "university of cambridge": "University of Cambridge",
    "unesco": "UNESCO",
    "oecd": "OECD",
    "world bank": "World Bank",
    "worldbank": "World Bank",
    "wb": "World Bank",
    "nsf": "National Science Foundation",
    "national science foundation": "National Science Foundation",
    "nces": "NCES",
    "nber": "NBER",
    "eric": "ERIC Education Database",
    "eric database": "ERIC Education Database",
    "kaggle": "Kaggle Academic Research",
    "uci": "UCI Machine Learning Repository",
    "owid": "Our World in Data",
    "our world in data": "Our World in Data",
}


DOC_TYPE_MAP: dict[str, list[str]] = {
    "research_paper": ["research_paper"],
    "research_papers": ["research_paper"],
    "research paper": ["research_paper"],
    "research papers": ["research_paper"],
    "academic paper": ["research_paper"],
    "academic papers": ["research_paper"],
    "paper": ["research_paper"],
    "papers": ["research_paper"],
    "study": ["research_paper"],
    "studies": ["research_paper"],
    "journal": ["research_paper"],
    "publication": ["research_paper"],
    "publications": ["research_paper"],
    "article": ["research_paper"],
    "articles": ["research_paper"],
    "syllabus": ["syllabus"],
    "syllabi": ["syllabus"],
    "course syllabus": ["syllabus"],
    "curriculum": ["syllabus"],
    "curricula": ["syllabus"],
    "course guide": ["syllabus"],
    "dataset": ["dataset"],
    "datasets": ["dataset"],
    "academic dataset": ["dataset"],
    "academic datasets": ["dataset"],
    "survey": ["dataset"],
    "survey data": ["dataset"],
    "csv": ["dataset"],
    "spreadsheet": ["spreadsheet"],
    "spreadsheets": ["spreadsheet"],
    "statistical spreadsheet": ["spreadsheet"],
    "workbook": ["spreadsheet"],
    "workbooks": ["spreadsheet"],
    "excel": ["spreadsheet"],
    "xlsx": ["spreadsheet"],
    "gradebook": ["spreadsheet"],
    "assessment matrix": ["spreadsheet"],
    "educational": ["educational"],
    "educational report": ["educational"],
    "report": ["educational"],
    "reports": ["educational"],
    "policy": ["educational"],
    "standard": ["educational"],
    "protocol": ["educational"],
}


def resolve_company_name(raw: str) -> str:
    """Normalize extracted entity or ticker to canonical corpus company name."""
    if not raw or not isinstance(raw, str):
        return raw
    cleaned = raw.strip().lower()
    return ALIAS_MAP.get(cleaned, raw.strip())


def resolve_document_type(raw: str) -> list[str] | None:
    """Normalize extracted document type to canonical corpus document types."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip().lower()
    return DOC_TYPE_MAP.get(cleaned)

# ─────────────────────────────────────────────────────────────────────────────
# Node implementations
# ─────────────────────────────────────────────────────────────────────────────


async def _node_contextualize_query(state: GraphState, provider: Any) -> GraphState:
    """Resolve conversational context and coreference from conversation history.

    CoT field — resolves 'continue', pronouns, or follow-ups into standalone queries.
    """
    history = state.get("conversation_history") or []
    question = state.get("question", "").strip()

    if not history or not question:
        state["contextualized_question"] = question
        return state

    CONTINUE_PHRASES = {
        "continue", "continue please", "please continue",
        "go on", "keep going", "carry on", "more", "tell me more",
        "proceed", "next", "expand", "elaborate", "finish", "resume",
        "continue the previous query", "continue previous", "carry on please",
    }
    q_norm = question.lower().strip().rstrip(".!?,")

    last_user_turn = None
    last_asst_turn = None
    for turn in reversed(history):
        role = str(turn.get("role", "")).lower()
        content = str(turn.get("content", "")).strip()
        if role == "user" and not last_user_turn and content and content.lower().strip().rstrip(".!?,") not in CONTINUE_PHRASES:
            last_user_turn = content
        elif role == "assistant" and not last_asst_turn and content:
            last_asst_turn = content
        if last_user_turn and last_asst_turn:
            break

    is_continuation = q_norm in CONTINUE_PHRASES

    # If the user says "continue" and we found the previous question
    if is_continuation and last_user_turn:
        # If assistant answer was empty, incomplete, or very short (< 50 chars), re-ask the original question thoroughly
        if not last_asst_turn or len(last_asst_turn) < 50:
            standalone = f"Answer in full detail: {last_user_turn}"
        else:
            standalone = f"Continue explaining and provide further details on: {last_user_turn}"
        state["contextualized_question"] = standalone
        state["question"] = standalone
        state["tool_calls"] = state.get("tool_calls", 0) + 1
        return state

    # Pronouns & short follow-up detection
    PRONOUNS = {"it", "its", "they", "them", "their", "this", "that", "these", "those", "he", "she"}
    words = set(q_norm.split())
    has_pronoun = bool(words & PRONOUNS)
    is_short_followup = len(words) <= 6 and (
        has_pronoun or q_norm.startswith(("what about", "how about", "why", "who", "when", "how", "and", "where"))
    )

    if is_continuation or is_short_followup or has_pronoun:
        try:
            messages = build_contextualize_query_messages(question, history)
            raw = await provider.generate(messages=messages, response_schema={})
            parsed = parse_json_content(raw["content"])
            standalone = parsed.get("standalone_query", "").strip()
            if standalone and len(standalone) >= 3:
                state["contextualized_question"] = standalone
                state["question"] = standalone
                state["tool_calls"] = state.get("tool_calls", 0) + 1
                return state
        except Exception as exc:
            logger.warning(
                "Contextual query rewriter failed; using fallback",
                extra={"extra": {"error": str(exc)}},
            )
            if last_user_turn:
                fallback = f"{last_user_turn} - {question}"
                state["contextualized_question"] = fallback
                state["question"] = fallback
                state["tool_calls"] = state.get("tool_calls", 0) + 1
                return state

    state["contextualized_question"] = question
    return state


async def _node_classify_query(state: GraphState, provider: Any) -> GraphState:
    """Classify the query type using the LLM.

    CoT field — result is never returned to the client.
    """
    messages = build_query_classification_messages(state["question"])
    try:
        raw = await provider.generate(messages=messages, response_schema={})
        parsed = parse_json_content(raw["content"])
    except (ProviderError, Exception) as exc:
        logger.warning(
            "classify_query failed, defaulting to DIRECT",
            extra={"extra": {"error": str(exc)}},
        )
        parsed = {}

    state["query_type"] = parsed.get("query_type", "DIRECT").upper()
    state["requires_calculation"] = bool(parsed.get("requires_calculation", False))
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


async def _node_extract_constraints(state: GraphState, provider: Any) -> GraphState:
    """Extract structured constraints from the question.

    CoT field — result is never returned to the client.
    """
    messages = build_constraint_extraction_messages(
        state["question"], state.get("query_type", "DIRECT")
    )
    try:
        raw = await provider.generate(messages=messages, response_schema={})
        parsed = parse_json_content(raw["content"])
    except (ProviderError, Exception) as exc:
        logger.warning(
            "extract_constraints failed, using empty constraints",
            extra={"extra": {"error": str(exc)}},
        )
        parsed = {}

    state["entities"] = parsed.get("entities") or []
    state["metric"] = parsed.get("metric") or None
    raw_year = parsed.get("time_period")
    try:
        state["time_period"] = int(raw_year) if raw_year else None
    except (TypeError, ValueError):
        state["time_period"] = None

    filters = parsed.get("filters") or {}
    state["retrieval_filters"] = {k: v for k, v in filters.items() if v is not None}
    core_topic = parsed.get("core_topic")
    if core_topic and isinstance(core_topic, str) and len(core_topic.strip()) > 3:
        state["retrieval_query"] = core_topic.strip()
    else:
        state["retrieval_query"] = state["question"]
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


def _node_apply_access_filter(state: GraphState) -> GraphState:
    """Inject authorized_document_ids into retrieval_filters and canonicalize company & doc types.

    Rule 12: Pre-retrieval authorization is applied here before any Qdrant call.
    The filter is built from the backend-resolved document ID list — never from
    user-supplied input.
    """
    import re
    auth_ids = state.get("authorized_document_ids", [])
    authorized_docs = state.get("authorized_documents", [])
    filters = dict(state.get("retrieval_filters", {}))
    filters.update(state.get("base_filters", {}))
    if auth_ids:
        filters["authorized_document_ids"] = auth_ids

    # Document routing: if user question or constraint targeted a specific document/book in corpus
    target_doc_title = filters.pop("document_title", None)
    matched_doc_id = None

    if target_doc_title and isinstance(target_doc_title, str) and target_doc_title.lower() != "null":
        t_clean = target_doc_title.lower().strip()
        for doc_meta in authorized_docs:
            d_title = doc_meta.get("title", "").lower().strip()
            if t_clean in d_title or d_title in t_clean:
                matched_doc_id = doc_meta.get("id")
                break

    if not matched_doc_id and authorized_docs:
        q_lower = state["question"].lower()
        # Search authorized documents sorted by title length descending
        for doc_meta in sorted(authorized_docs, key=lambda d: len(d.get("title", "")), reverse=True):
            raw_title = doc_meta.get("title", "")
            clean_title = re.sub(r"\[.*?\]", "", raw_title).strip().lower()
            if len(clean_title) >= 5 and clean_title in q_lower:
                matched_doc_id = doc_meta.get("id")
                break
            if "deep learning" in clean_title and "deep learning" in q_lower:
                matched_doc_id = doc_meta.get("id")
                break

    if matched_doc_id:
        filters["document_id"] = matched_doc_id
        # Strip conversational document reference from retrieval query to maximize chunk relevance
        curr_q = state.get("retrieval_query", state["question"])
        refined_q = re.sub(
            r"(?i)\b(from|in|according to|based on|out of)\s+(the\s+)?(book|paper|document|corpus|syllabus)\b.*$",
            "",
            curr_q,
        ).strip()
        if len(refined_q) >= 3:
            state["retrieval_query"] = refined_q

    company = filters.get("company") or filters.get("companies")
    if company:
        if isinstance(company, str):
            resolved = resolve_company_name(company)
            filters["company"] = resolved
            filters["companies"] = [resolved]
        elif isinstance(company, list):
            resolved_list = [resolve_company_name(c) for c in company if isinstance(c, str)]
            filters["company"] = resolved_list
            filters["companies"] = resolved_list

    # Canonical document_type resolution
    doc_type = filters.get("document_type") or filters.get("document_types")
    if doc_type:
        if isinstance(doc_type, str):
            resolved_dt = resolve_document_type(doc_type)
            if resolved_dt:
                filters["document_type"] = resolved_dt
                filters["document_types"] = resolved_dt
            else:
                filters.pop("document_type", None)
                filters.pop("document_types", None)
        elif isinstance(doc_type, list):
            resolved_dt_list = []
            for dt in doc_type:
                res = resolve_document_type(dt)
                if res:
                    resolved_dt_list.extend(res)
            if resolved_dt_list:
                filters["document_type"] = list(set(resolved_dt_list))
                filters["document_types"] = list(set(resolved_dt_list))
            else:
                filters.pop("document_type", None)
                filters.pop("document_types", None)

    # Also resolve entities for comparison workflow if present
    entities = state.get("entities", [])
    if entities:
        state["entities"] = [resolve_company_name(e) for e in entities if isinstance(e, str)]

    state["retrieval_filters"] = filters
    state["retrieval_attempts"] = state.get("retrieval_attempts", 0)
    state["evidence"] = state.get("evidence", [])
    return state


def _node_retrieve(state: GraphState, retriever: Any) -> GraphState:
    """Run hybrid retrieval with the current query and access-controlled filters."""
    query = state.get("retrieval_query") or state["question"]
    filters = state.get("retrieval_filters", {})
    try:
        results, _ = retriever.retrieve(query=query, filters=filters)
        state["evidence"] = results
    except Exception as exc:
        logger.warning(
            "Retriever error during graph retrieval node; continuing with empty evidence",
            extra={"extra": {"error": str(exc)}},
        )
        state["evidence"] = []
    state["retrieval_attempts"] = state.get("retrieval_attempts", 0) + 1
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


def _assess_evidence(evidence: list[RetrievalResult], min_score: float = 0.05) -> bool:
    """Return True if there is retrieved evidence with sufficient relevance to attempt generation."""
    if not evidence:
        return False
    return any(getattr(e, "score", 0.0) >= min_score for e in evidence)


def _node_assess_evidence(state: GraphState) -> GraphState:
    """Assess whether retrieved evidence is sufficient to generate an answer."""
    state["evidence_sufficient"] = _assess_evidence(state.get("evidence", []))
    return state


async def _node_expand_query(state: GraphState, provider: Any) -> GraphState:
    """Expand the retrieval query when evidence was insufficient.

    CoT operation — only affects retrieval_query, not the final response.
    """
    evidence_summary = f"{len(state.get('evidence', []))} chunks found with low relevance"
    messages = build_expansion_messages(state["question"], evidence_summary)
    try:
        raw = await provider.generate(messages=messages, response_schema={})
        parsed = parse_json_content(raw["content"])
        expanded = parsed.get("expanded_query", "").strip()
        if expanded:
            state["retrieval_query"] = expanded
    except (ProviderError, Exception) as exc:
        logger.warning(
            "expand_query failed, keeping original query",
            extra={"extra": {"error": str(exc)}},
        )
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


async def _node_retrieve_comparison(
    state: GraphState, generator: RAGGenerator, retriever: Any
) -> GraphState:
    """Retrieve independent evidence for each entity (comparison path)."""
    entities = state.get("entities", [])
    if not entities or len(entities) < 2:
        # Conceptual comparison without multi-entity retrieval requirement
        result = await generator.generate(
            question=state["question"],
            evidence=state.get("evidence", []),
            query_type="COMPARISON",
            conversation_history=state.get("conversation_history"),
        )
        state["result"] = result
        state["tool_calls"] = state.get("tool_calls", 0) + 1
        return state

    wf = ComparisonWorkflow(generator=generator, retriever=retriever)
    result = await wf.run(
        question=state["question"],
        entities=entities,
        metric=state.get("metric"),
        authorized_document_ids=state.get("authorized_document_ids", []),
        time_period=state.get("time_period"),
        extra_filters={
            k: v
            for k, v in state.get("retrieval_filters", {}).items()
            if k != "authorized_document_ids"
        },
    )
    # If comparison workflow yielded no grounded result but we already have retrieved evidence, fall back to it
    if (result.abstained or not result.grounded) and state.get("evidence"):
        fallback_res = await generator.generate(
            question=state["question"],
            evidence=state.get("evidence", []),
            query_type="COMPARISON",
            conversation_history=state.get("conversation_history"),
        )
        if not fallback_res.abstained:
            result = fallback_res

    state["result"] = result
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


async def _node_calculate(state: GraphState, generator: RAGGenerator) -> GraphState:
    """Run numerical workflow for numerical questions."""
    wf = NumericalWorkflow(generator=generator)
    result = await wf.run(
        question=state["question"],
        evidence=state.get("evidence", []),
    )
    state["result"] = result
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


async def _node_generate(state: GraphState, generator: RAGGenerator) -> GraphState:
    """Standard RAG generation (sufficient evidence path)."""
    query_type = state.get("query_type", "DIRECT")

    if query_type == "TEMPORAL":
        wf = TemporalWorkflow(generator=generator)
        result = await wf.run(
            question=state["question"],
            evidence=state.get("evidence", []),
            requested_year=state.get("time_period"),
        )
    else:
        result = await generator.generate(
            question=state["question"],
            evidence=state.get("evidence", []),
            query_type=query_type,
            conversation_history=state.get("conversation_history"),
        )

    state["result"] = result
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    return state


def _node_validate_citations(state: GraphState) -> GraphState:
    """Cross-check citation IDs in result against retrieved evidence (Rule 12)."""
    result = state.get("result")
    evidence = state.get("evidence", [])
    if result is not None and evidence:
        verified = validate_citations(result.citation_ids, evidence)
        # Rebuild result with validated IDs only
        state["result"] = GenerationResult(
            answer=result.answer,
            citation_ids=verified,
            grounded=result.grounded and bool(verified),
            abstained=result.abstained,
            query_type=result.query_type,
            token_usage=result.token_usage,
            evidence=evidence,
        )
    return state


def _node_finalize(state: GraphState) -> GraphState:
    """Produce a clean final result, abstracting on failure.

    Guarantees state["result"] is always set.
    Internal CoT state is NOT cleared here — callers must only read state["result"].
    """
    if state.get("result") is None:
        state["result"] = GenerationResult(
            answer=(
                "I was unable to find sufficient evidence in the available documents "
                "to answer this question."
            ),
            citation_ids=[],
            grounded=False,
            abstained=True,
            query_type=state.get("query_type", "DIRECT"),
        )
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Routing logic
# ─────────────────────────────────────────────────────────────────────────────


def _route_after_evidence_assessment(
    state: GraphState,
    max_retrieval_attempts: int,
    max_tool_calls: int,
) -> str:
    """Conditional router after assess_evidence node.

    Returns the name of the next node to execute.
    """
    tool_calls = state.get("tool_calls", 0)
    retrieval_attempts = state.get("retrieval_attempts", 0)
    query_type = state.get("query_type", "DIRECT")
    evidence_sufficient = state.get("evidence_sufficient", False)

    # Hard stop: tool-call budget exhausted
    if tool_calls >= max_tool_calls:
        logger.warning(
            "Agent max_tool_calls reached; finalising",
            extra={"extra": {"tool_calls": tool_calls}},
        )
        return "generate"

    if not evidence_sufficient and retrieval_attempts < max_retrieval_attempts:
        return "expand_query"

    if query_type == "NUMERICAL" and state.get("requires_calculation", False):
        return "calculate"

    if query_type == "COMPARISON" and len(state.get("entities", [])) >= 2:
        return "retrieve_comparison"

    return "generate"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point: RAGGraph
# ─────────────────────────────────────────────────────────────────────────────


class RAGGraph:
    """Agentic RAG orchestrator using LangGraph.

    This class wires all nodes and routing logic into a compiled graph.
    Services are injected — not imported globally — to enable testability.

    Rule 11: CoT graph state is never returned; only state["result"] is exposed.
    Rule 15: max_retrieval_attempts and max_tool_calls are hard limits.
    """

    def __init__(
        self,
        provider: Any,
        retriever: Any,
        generator: RAGGenerator,
        max_retrieval_attempts: int = 3,
        max_tool_calls: int = 10,
    ) -> None:
        self._provider = provider
        self._retriever = retriever
        self._generator = generator
        self._max_retrieval_attempts = max_retrieval_attempts
        self._max_tool_calls = max_tool_calls

        self._graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Compile the LangGraph StateGraph."""
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise ImportError(
                "langgraph is required for Phase 11. Install it: pip install langgraph"
            ) from exc

        graph = StateGraph(GraphState)

        # Register nodes with bound service references
        provider = self._provider
        retriever = self._retriever
        generator = self._generator
        max_r = self._max_retrieval_attempts
        max_t = self._max_tool_calls

        async def contextualize_query_node(s: GraphState) -> GraphState:
            return await _node_contextualize_query(s, provider)

        async def classify_query_node(s: GraphState) -> GraphState:
            return await _node_classify_query(s, provider)

        async def extract_constraints_node(s: GraphState) -> GraphState:
            return await _node_extract_constraints(s, provider)

        async def expand_query_node(s: GraphState) -> GraphState:
            return await _node_expand_query(s, provider)

        async def retrieve_comparison_node(s: GraphState) -> GraphState:
            return await _node_retrieve_comparison(s, generator, retriever)

        async def calculate_node(s: GraphState) -> GraphState:
            return await _node_calculate(s, generator)

        async def generate_node(s: GraphState) -> GraphState:
            return await _node_generate(s, generator)

        graph.add_node("contextualize_query", contextualize_query_node)
        graph.add_node("classify_query", classify_query_node)
        graph.add_node("extract_constraints", extract_constraints_node)
        graph.add_node("apply_access_filter", _node_apply_access_filter)
        graph.add_node("retrieve", lambda s: _node_retrieve(s, retriever))
        graph.add_node("assess_evidence", _node_assess_evidence)
        graph.add_node("expand_query", expand_query_node)
        graph.add_node("retrieve_comparison", retrieve_comparison_node)
        graph.add_node("calculate", calculate_node)
        graph.add_node("generate", generate_node)
        graph.add_node("validate_citations", _node_validate_citations)
        graph.add_node("finalize", _node_finalize)

        # Edges — linear path
        graph.add_edge(START, "contextualize_query")
        graph.add_edge("contextualize_query", "classify_query")
        graph.add_edge("classify_query", "extract_constraints")
        graph.add_edge("extract_constraints", "apply_access_filter")
        graph.add_edge("apply_access_filter", "retrieve")
        graph.add_edge("retrieve", "assess_evidence")

        # Conditional routing after evidence assessment
        graph.add_conditional_edges(
            "assess_evidence",
            lambda s: _route_after_evidence_assessment(s, max_r, max_t),
            {
                "expand_query": "expand_query",
                "calculate": "calculate",
                "retrieve_comparison": "retrieve_comparison",
                "generate": "generate",
            },
        )

        # After expansion → retrieve again (loop back, bounded by retrieval_attempts)
        graph.add_edge("expand_query", "retrieve")

        # All generation paths converge at validate_citations → finalize
        graph.add_edge("retrieve_comparison", "validate_citations")
        graph.add_edge("calculate", "validate_citations")
        graph.add_edge("generate", "validate_citations")
        graph.add_edge("validate_citations", "finalize")
        graph.add_edge("finalize", END)

        return graph.compile()

    async def run(
        self,
        question: str,
        authorized_document_ids: list[str],
        user_id: str,
        base_filters: dict[str, Any] | None = None,
        authorized_documents: list[dict[str, str]] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> GenerationResult:
        """Execute the agentic RAG pipeline.

        Args:
            question: Sanitised user question (validated by the API layer).
            authorized_document_ids: Backend-resolved list of document IDs the
                                     user is allowed to access (Rule 12).
            user_id: User identifier for audit logging.
            base_filters: Optional metadata filters from the API request.
            authorized_documents: List of authorized document metadata {id, title, organization}.
            conversation_history: Optional list of previous conversation turns {role, content}.

        Returns:
            GenerationResult — only the public fields; CoT state is discarded.
        """
        initial_state: GraphState = {
            "question": question,
            "conversation_history": conversation_history or [],
            "contextualized_question": None,
            "authorized_document_ids": authorized_document_ids,
            "authorized_documents": authorized_documents or [],
            "user_id": user_id,
            "base_filters": base_filters or {},
            "retrieval_attempts": 0,
            "tool_calls": 0,
            "evidence": [],
            "result": None,
            "error": None,
        }

        try:
            final_state = await self._graph.ainvoke(initial_state)
        except Exception as exc:
            logger.error(
                "RAGGraph execution failed",
                extra={"extra": {"user_id": user_id, "error": type(exc).__name__}},
            )
            return GenerationResult(
                answer=(
                    "An error occurred while processing your query. "
                    "Please try again or contact support."
                ),
                citation_ids=[],
                grounded=False,
                abstained=True,
                query_type="DIRECT",
            )

        result = final_state.get("result")
        if result is None:
            return GenerationResult(
                answer=("I was unable to find sufficient evidence to answer this question."),
                citation_ids=[],
                grounded=False,
                abstained=True,
                query_type="DIRECT",
            )

        # Discard CoT state — return only the generation result (Rule 11)
        return result

    async def astream_run(
        self,
        question: str,
        authorized_document_ids: list[str],
        user_id: str,
        base_filters: dict[str, Any] | None = None,
        authorized_documents: list[dict[str, str]] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the agentic RAG pipeline yielding real-time step progress and final result."""
        initial_state: GraphState = {
            "question": question,
            "conversation_history": conversation_history or [],
            "contextualized_question": None,
            "authorized_document_ids": authorized_document_ids,
            "authorized_documents": authorized_documents or [],
            "user_id": user_id,
            "base_filters": base_filters or {},
            "retrieval_attempts": 0,
            "tool_calls": 0,
            "evidence": [],
            "result": None,
            "error": None,
        }

        step_descriptions: dict[str, tuple[str, str]] = {
            "contextualize_query": ("Resolving conversation context", "Interpreting query within conversation history..."),
            "classify_query": ("Analyzing query intent", "Classifying research question scope and analytical type..."),
            "extract_constraints": ("Extracting constraints", "Identifying institutions, time periods, and topics..."),
            "apply_access_filter": ("Verifying permissions", "Applying security boundaries and index constraints..."),
            "retrieve": ("Searching knowledge base", "Retrieving candidate evidence passages from vector & keyword index..."),
            "assess_evidence": ("Evaluating evidence", "Analyzing passage relevance and grounded coverage..."),
            "calculate": ("Executing numerical analysis", "Computing metrics and quantitative indicators..."),
            "retrieve_comparison": ("Cross-referencing entities", "Retrieving comparative datasets across entities..."),
            "expand_query": ("Expanding search scope", "Refining retrieval terms for broader coverage..."),
            "generate": ("Synthesizing research response", "Drafting evidence-grounded academic response with citations..."),
            "validate_citations": ("Verifying citations", "Cross-checking citations against retrieved sources..."),
            "finalize": ("Finalizing response", "Packaging answer and grounded evidence..."),
        }

        current_state: dict[str, Any] = dict(initial_state)

        try:
            async for chunk in self._graph.astream(initial_state, stream_mode="updates"):
                for node_name, updated_fields in chunk.items():
                    current_state.update(updated_fields)
                    title, default_detail = step_descriptions.get(
                        node_name, (node_name.replace("_", " ").title(), "Completed step")
                    )
                    detail = default_detail

                    if node_name == "contextualize_query":
                        ctx_q = updated_fields.get("contextualized_question")
                        if ctx_q and ctx_q != initial_state["question"]:
                            detail = f"Interpreted as: {ctx_q[:80]}..."
                        else:
                            detail = "Query is standalone"
                    elif node_name == "classify_query":
                        q_type = updated_fields.get("query_type", "DIRECT")
                        detail = f"Classified query type as {q_type}"
                    elif node_name == "extract_constraints":
                        entities = updated_fields.get("entities") or []
                        if entities:
                            detail = f"Identified entities: {', '.join(entities[:3])}"
                    elif node_name == "retrieve":
                        ev_count = len(current_state.get("evidence", []))
                        detail = f"Retrieved {ev_count} candidate passages from academic corpus"
                    elif node_name == "validate_citations":
                        res = current_state.get("result")
                        c_count = len(res.citation_ids) if res else 0
                        detail = f"Verified {c_count} source citations for factual grounding"

                    yield {
                        "type": "step",
                        "node": node_name,
                        "title": title,
                        "detail": detail,
                        "status": "completed",
                    }
        except Exception as exc:
            logger.error(
                "RAGGraph astream execution failed",
                extra={"extra": {"user_id": user_id, "error": type(exc).__name__}},
            )
            yield {
                "type": "result",
                "result": GenerationResult(
                    answer="An error occurred while processing your query. Please try again or contact support.",
                    citation_ids=[],
                    grounded=False,
                    abstained=True,
                    query_type="DIRECT",
                ),
            }
            return

        result = current_state.get("result")
        if result is None:
            result = GenerationResult(
                answer="I was unable to find sufficient evidence to answer this question.",
                citation_ids=[],
                grounded=False,
                abstained=True,
                query_type="DIRECT",
            )

        yield {
            "type": "result",
            "result": result,
        }
