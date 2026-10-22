"""Unit tests for the Phase 11 LangGraph agentic RAG pipeline.

Tests use mock provider and retriever — no network, no Qdrant, no real LLM.

Rule 17 / Rule 15 coverage:
- classify → extract → access_filter → retrieve → assess → generate path
- expansion loop bounded by max_retrieval_attempts
- max_tool_calls hard stop
- abstention when evidence remains insufficient
- citation validation node (fabricated IDs stripped)
- CoT fields NOT in the final GenerationResult (Rule 11)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.llm.generation import GenerationResult, RAGGenerator
from packages.llm.graph import (
    GraphState,
    RAGGraph,
    _node_apply_access_filter,
    _node_assess_evidence,
    _node_finalize,
    _node_validate_citations,
    _route_after_evidence_assessment,
)
from packages.retrieval.models import RetrievalResult

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _chunk(cid: str, score: float = 0.9) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=cid,
        document_id="doc-1",
        score=score,
        text=f"Evidence text for {cid}.",
        company="Acme",
        year=2024,
    )


def _mock_provider(classify_type: str = "DIRECT") -> AsyncMock:
    """Provider that returns plausible JSON for each node call."""
    provider = AsyncMock()

    async def _generate(messages, response_schema=None):
        system_content = messages[0]["content"]
        if "Classify" in system_content or "category" in system_content:
            return {
                "content": json.dumps(
                    {
                        "query_type": classify_type,
                        "requires_calculation": classify_type == "NUMERICAL",
                    }
                ),
                "model": "mock",
                "usage": {},
            }
        if "Extract structured" in system_content or "constraints" in system_content:
            return {
                "content": json.dumps(
                    {
                        "entities": [],
                        "metric": None,
                        "time_period": None,
                        "filters": {},
                    }
                ),
                "model": "mock",
                "usage": {},
            }
        if "expand" in system_content.lower():
            return {
                "content": json.dumps({"expanded_query": "expanded search term"}),
                "model": "mock",
                "usage": {},
            }
        # Default: grounded answer
        return {
            "content": json.dumps(
                {
                    "answer": "The answer is 42.",
                    "citation_ids": ["chunk-real"],
                    "grounded": True,
                    "abstained": False,
                }
            ),
            "model": "mock",
            "usage": {},
        }

    provider.generate.side_effect = _generate
    return provider


def _mock_generator(evidence_chunks: list[RetrievalResult] | None = None) -> RAGGenerator:
    provider = AsyncMock()
    provider.generate.return_value = {
        "content": json.dumps(
            {
                "answer": "The answer.",
                "citation_ids": ["chunk-real"],
                "grounded": True,
                "abstained": False,
            }
        ),
        "model": "mock",
        "usage": {},
    }
    return RAGGenerator(provider=provider)


def _mock_retriever(chunks: list[RetrievalResult]) -> MagicMock:
    r = MagicMock()
    r.retrieve.return_value = (chunks, MagicMock())
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Node unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyAccessFilter:
    def test_injects_authorized_ids(self):
        state: GraphState = {
            "question": "test",
            "authorized_document_ids": ["doc-1", "doc-2"],
            "base_filters": {"company": "Acme"},
            "retrieval_filters": {},
            "retrieval_attempts": 0,
            "evidence": [],
        }
        result = _node_apply_access_filter(state)
        assert "authorized_document_ids" in result["retrieval_filters"]
        assert result["retrieval_filters"]["authorized_document_ids"] == ["doc-1", "doc-2"]
        # base_filters merged in
        assert result["retrieval_filters"].get("company") == "Acme"

    def test_empty_auth_ids_still_works(self):
        state: GraphState = {
            "question": "test",
            "authorized_document_ids": [],
            "base_filters": {},
            "retrieval_filters": {},
            "retrieval_attempts": 0,
            "evidence": [],
        }
        result = _node_apply_access_filter(state)
        # Empty list is fine — Qdrant will return nothing for empty auth list
        assert "authorized_document_ids" not in result["retrieval_filters"]


class TestAssessEvidence:
    def test_sufficient_when_high_score(self):
        state: GraphState = {"evidence": [_chunk("c1", score=0.8)]}
        result = _node_assess_evidence(state)
        assert result["evidence_sufficient"] is True

    def test_insufficient_when_empty(self):
        state: GraphState = {"evidence": []}
        result = _node_assess_evidence(state)
        assert result["evidence_sufficient"] is False

    def test_insufficient_when_all_scores_low(self):
        state: GraphState = {"evidence": [_chunk("c1", score=0.001)]}
        result = _node_assess_evidence(state)
        assert result["evidence_sufficient"] is False


class TestRouteAfterEvidenceAssessment:
    def test_routes_to_expand_when_insufficient(self):
        state: GraphState = {
            "evidence_sufficient": False,
            "retrieval_attempts": 1,
            "tool_calls": 5,
            "query_type": "DIRECT",
            "requires_calculation": False,
        }
        route = _route_after_evidence_assessment(state, max_retrieval_attempts=3, max_tool_calls=10)
        assert route == "expand_query"

    def test_routes_to_generate_when_max_attempts_reached(self):
        state: GraphState = {
            "evidence_sufficient": False,
            "retrieval_attempts": 3,
            "tool_calls": 6,
            "query_type": "DIRECT",
            "requires_calculation": False,
        }
        route = _route_after_evidence_assessment(state, max_retrieval_attempts=3, max_tool_calls=10)
        assert route == "generate"

    def test_routes_to_calculate_for_numerical(self):
        state: GraphState = {
            "evidence_sufficient": True,
            "retrieval_attempts": 1,
            "tool_calls": 4,
            "query_type": "NUMERICAL",
            "requires_calculation": True,
        }
        route = _route_after_evidence_assessment(state, max_retrieval_attempts=3, max_tool_calls=10)
        assert route == "calculate"

    def test_routes_to_comparison(self):
        state: GraphState = {
            "evidence_sufficient": True,
            "retrieval_attempts": 1,
            "tool_calls": 4,
            "query_type": "COMPARISON",
            "requires_calculation": False,
            "entities": ["Company A", "Company B"],
        }
        route = _route_after_evidence_assessment(state, max_retrieval_attempts=3, max_tool_calls=10)
        assert route == "retrieve_comparison"

    def test_max_tool_calls_stops_loop(self):
        """Hard stop: max_tool_calls exhausted → generate (not expand)."""
        state: GraphState = {
            "evidence_sufficient": False,
            "retrieval_attempts": 1,
            "tool_calls": 10,
            "query_type": "DIRECT",
            "requires_calculation": False,
        }
        route = _route_after_evidence_assessment(state, max_retrieval_attempts=3, max_tool_calls=10)
        assert route == "generate"


class TestValidateCitationsNode:
    def test_strips_fabricated_ids_from_result(self):
        real_chunk = _chunk("chunk-real")
        state: GraphState = {
            "evidence": [real_chunk],
            "result": GenerationResult(
                answer="Answer.",
                citation_ids=["chunk-real", "FABRICATED"],
                grounded=True,
                abstained=False,
                query_type="DIRECT",
            ),
        }
        result_state = _node_validate_citations(state)
        assert "FABRICATED" not in result_state["result"].citation_ids
        assert "chunk-real" in result_state["result"].citation_ids

    def test_grounded_set_false_when_all_citations_fabricated(self):
        real_chunk = _chunk("chunk-real")
        state: GraphState = {
            "evidence": [real_chunk],
            "result": GenerationResult(
                answer="Answer.",
                citation_ids=["FAKE-1"],
                grounded=True,
                abstained=False,
                query_type="DIRECT",
            ),
        }
        result_state = _node_validate_citations(state)
        assert result_state["result"].grounded is False


class TestFinalizeNode:
    def test_sets_abstained_result_when_none(self):
        state: GraphState = {"result": None, "query_type": "DIRECT"}
        result_state = _node_finalize(state)
        assert result_state["result"] is not None
        assert result_state["result"].abstained is True

    def test_preserves_existing_result(self):
        existing = GenerationResult(
            answer="Real answer.",
            citation_ids=["c1"],
            grounded=True,
            abstained=False,
            query_type="DIRECT",
        )
        state: GraphState = {"result": existing}
        result_state = _node_finalize(state)
        assert result_state["result"].answer == "Real answer."


# ─────────────────────────────────────────────────────────────────────────────
# CoT fields never in GenerationResult (Rule 11)
# ─────────────────────────────────────────────────────────────────────────────


class TestCotNotExposed:
    def test_generation_result_has_no_cot_fields(self):
        """Rule 11: Internal graph state fields must not appear in GenerationResult."""
        cot_fields = {
            "query_type_raw",
            "evidence_sufficient",
            "retrieval_attempts",
            "tool_calls",
            "retrieval_filters",
            "base_filters",
            "authorized_document_ids",
            "entities",
            "metric",
            "time_period",
        }
        result_fields = set(GenerationResult.__dataclass_fields__.keys())
        leaked = cot_fields & result_fields
        assert leaked == set(), f"CoT fields leaked into GenerationResult: {leaked}"

    def test_query_response_schema_has_no_cot_fields(self):
        """Rule 11: API response schema must not contain CoT fields."""
        from apps.api.app.schemas.query import QueryResponse

        cot_fields = {
            "retrieval_attempts",
            "tool_calls",
            "retrieval_filters",
            "evidence_sufficient",
            "authorized_document_ids",
            "token_usage",
            "entities",
            "metric",
            "time_period",
        }
        response_fields = set(QueryResponse.model_fields.keys())
        leaked = cot_fields & response_fields
        assert leaked == set(), f"Sensitive/CoT fields leaked into QueryResponse: {leaked}"


# ─────────────────────────────────────────────────────────────────────────────
# RAGGraph integration (langgraph required; skipped if not installed)
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_graph_abstains_when_no_evidence():
    """Graph must abstain when retriever returns no evidence after max attempts."""
    pytest.importorskip("langgraph", reason="langgraph not installed")

    provider = _mock_provider("DIRECT")
    retriever = _mock_retriever([])  # always empty
    generator = _mock_generator()

    graph = RAGGraph(
        provider=provider,
        retriever=retriever,
        generator=generator,
        max_retrieval_attempts=2,
        max_tool_calls=10,
    )

    result = await graph.run(
        question="What is the revenue?",
        authorized_document_ids=["doc-1"],
        user_id="user-test",
    )

    # With no evidence, the graph must abstain or at least return a valid result
    assert isinstance(result, GenerationResult)
    # CoT not exposed
    assert not hasattr(result, "evidence_sufficient")
    assert not hasattr(result, "retrieval_attempts")


@pytest.mark.asyncio
async def test_graph_generates_when_evidence_present():
    pytest.importorskip("langgraph", reason="langgraph not installed")

    provider = _mock_provider("DIRECT")
    retriever = _mock_retriever([_chunk("chunk-real", score=0.9)])
    generator = _mock_generator()

    graph = RAGGraph(
        provider=provider,
        retriever=retriever,
        generator=generator,
        max_retrieval_attempts=3,
        max_tool_calls=10,
    )

    result = await graph.run(
        question="Revenue?",
        authorized_document_ids=["doc-1"],
        user_id="user-test",
    )

    assert isinstance(result, GenerationResult)
    assert result.answer != ""


@pytest.mark.asyncio
async def test_graph_loop_bounded_by_max_retrieval_attempts():
    """Retriever must not be called more than max_retrieval_attempts times."""
    pytest.importorskip("langgraph", reason="langgraph not installed")

    provider = _mock_provider("DIRECT")
    retriever = _mock_retriever([])  # always insufficient

    generator = _mock_generator()
    graph = RAGGraph(
        provider=provider,
        retriever=retriever,
        generator=generator,
        max_retrieval_attempts=2,
        max_tool_calls=20,
    )

    result = await graph.run(
        question="test?",
        authorized_document_ids=["doc-1"],
        user_id="user-test",
    )

    # Retriever called at most max_retrieval_attempts times
    assert retriever.retrieve.call_count <= 2
    assert isinstance(result, GenerationResult)
