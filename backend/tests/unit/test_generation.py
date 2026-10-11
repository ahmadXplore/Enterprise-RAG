"""Unit tests for RAG generation, citation validation, and provider abstractions.

Phase 9 tests — no network calls, no real LLM.
All providers are mocked to test the generation pipeline in isolation.

Rule 17: Tests cover authorized access, citation validation, abstention,
         fabricated-citation stripping, and sensitive-field exposure.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from packages.llm.generation import GenerationResult, RAGGenerator, validate_citations
from packages.llm.prompt import build_rag_messages
from packages.llm.providers import (
    GroqProvider,
    OllamaProvider,
    OpenRouterProvider,
    ProviderError,
    build_provider,
    parse_json_content,
)
from packages.retrieval.models import RetrievalResult

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def evidence_chunks() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk_id="chunk-001",
            document_id="doc-apple-2024",
            score=0.95,
            text="Apple iPhone net sales were $201,183 million in fiscal 2024.",
            company="Apple Inc.",
            year=2024,
            section="MD&A > iPhone",
            page_start=25,
            page_end=26,
        ),
        RetrievalResult(
            chunk_id="chunk-002",
            document_id="doc-apple-2024",
            score=0.88,
            text="Apple Services revenue reached $96,169 million in fiscal 2024.",
            company="Apple Inc.",
            year=2024,
            section="MD&A > Services",
            page_start=27,
            page_end=28,
        ),
    ]


def _make_provider_mock(content: str) -> AsyncMock:
    """Return an AsyncMock that simulates a successful LLM generate() call."""
    mock = AsyncMock()
    mock.generate.return_value = {"content": content, "model": "mock", "usage": {}}
    return mock


# ─────────────────────────────────────────────────────────────────────────────
# parse_json_content
# ─────────────────────────────────────────────────────────────────────────────


class TestParseJsonContent:
    def test_parses_valid_json(self):
        raw = '{"answer": "test", "citation_ids": ["c1"]}'
        result = parse_json_content(raw)
        assert result["answer"] == "test"

    def test_strips_markdown_fences(self):
        raw = '```json\n{"answer": "ok"}\n```'
        result = parse_json_content(raw)
        assert result["answer"] == "ok"

    def test_returns_empty_dict_on_invalid_json(self):
        result = parse_json_content("not json at all {{")
        assert result == {}

    def test_returns_empty_dict_on_empty_string(self):
        assert parse_json_content("") == {}


# ─────────────────────────────────────────────────────────────────────────────
# validate_citations — Rule 12
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateCitations:
    def test_keeps_valid_ids(self, evidence_chunks):
        result = validate_citations(["chunk-001", "chunk-002"], evidence_chunks)
        assert result == ["chunk-001", "chunk-002"]

    def test_strips_fabricated_ids(self, evidence_chunks):
        result = validate_citations(["chunk-001", "FAKE-999"], evidence_chunks)
        assert result == ["chunk-001"]
        assert "FAKE-999" not in result

    def test_all_fabricated_returns_empty(self, evidence_chunks):
        result = validate_citations(["FAKE-A", "FAKE-B"], evidence_chunks)
        assert result == []

    def test_empty_claimed_ids(self, evidence_chunks):
        assert validate_citations([], evidence_chunks) == []

    def test_empty_evidence(self):
        result = validate_citations(["chunk-001"], [])
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# RAGGenerator — Phase 9 pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestRAGGenerator:
    @pytest.mark.asyncio
    async def test_grounded_response(self, evidence_chunks):
        llm_output = json.dumps(
            {
                "answer": "iPhone net sales were $201 billion in fiscal 2024.",
                "citation_ids": ["chunk-001"],
                "grounded": True,
                "abstained": False,
            }
        )
        provider = _make_provider_mock(llm_output)
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="What were iPhone sales?", evidence=evidence_chunks)

        assert isinstance(result, GenerationResult)
        assert result.grounded is True
        assert result.abstained is False
        assert "chunk-001" in result.citation_ids
        assert result.answer != ""

    @pytest.mark.asyncio
    async def test_abstains_with_no_evidence(self):
        provider = _make_provider_mock("{}")
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="What is revenue?", evidence=[])

        assert result.abstained is True
        assert result.grounded is False
        assert result.citation_ids == []
        # LLM should not be called if there is no evidence
        provider.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_fabricated_citations_stripped(self, evidence_chunks):
        llm_output = json.dumps(
            {
                "answer": "iPhone sales were high.",
                "citation_ids": ["chunk-001", "INVENTED-XYZ"],
                "grounded": True,
                "abstained": False,
            }
        )
        provider = _make_provider_mock(llm_output)
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="iPhone sales?", evidence=evidence_chunks)

        assert "INVENTED-XYZ" not in result.citation_ids
        assert "chunk-001" in result.citation_ids

    @pytest.mark.asyncio
    async def test_grounded_false_when_all_citations_fabricated(self, evidence_chunks):
        llm_output = json.dumps(
            {
                "answer": "Revenue was $100B.",
                "citation_ids": ["FAKE-1", "FAKE-2"],
                "grounded": True,
                "abstained": False,
            }
        )
        provider = _make_provider_mock(llm_output)
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="Revenue?", evidence=evidence_chunks)

        assert result.citation_ids == []
        assert result.grounded is False  # corrected from LLM's false claim

    @pytest.mark.asyncio
    async def test_abstained_set_on_empty_llm_answer(self, evidence_chunks):
        llm_output = json.dumps(
            {
                "answer": "",
                "citation_ids": [],
                "grounded": False,
                "abstained": False,
            }
        )
        provider = _make_provider_mock(llm_output)
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="What?", evidence=evidence_chunks)

        assert result.abstained is True

    @pytest.mark.asyncio
    async def test_provider_error_propagates(self, evidence_chunks):
        provider = AsyncMock()
        provider.generate.side_effect = ProviderError("groq", "Service unavailable", 503)
        gen = RAGGenerator(provider=provider)

        with pytest.raises(ProviderError):
            await gen.generate(question="What?", evidence=evidence_chunks)

    @pytest.mark.asyncio
    async def test_token_usage_not_in_generation_result_public_fields(self, evidence_chunks):
        """Rule 6: token_usage must not leak into API response schema fields."""
        llm_output = json.dumps(
            {
                "answer": "Sales were high.",
                "citation_ids": ["chunk-001"],
                "grounded": True,
                "abstained": False,
            }
        )
        provider = _make_provider_mock(llm_output)
        provider.generate.return_value = {
            "content": llm_output,
            "model": "mock",
            "usage": {"prompt_tokens": 500, "completion_tokens": 200},
        }
        gen = RAGGenerator(provider=provider)
        result = await gen.generate(question="Sales?", evidence=evidence_chunks)
        assert result.answer

        # token_usage is stored but must not appear in QueryResponse schema
        from apps.api.app.schemas.query import QueryResponse

        response_fields = set(QueryResponse.model_fields.keys())
        assert "token_usage" not in response_fields


# ─────────────────────────────────────────────────────────────────────────────
# Prompt builder
# ─────────────────────────────────────────────────────────────────────────────


class TestPromptBuilder:
    def test_builds_messages_with_evidence(self, evidence_chunks):
        messages = build_rag_messages("What were iPhone sales?", evidence_chunks)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "chunk-001" in messages[1]["content"]
        assert "chunk-002" in messages[1]["content"]

    def test_evidence_truncated_at_max_chars(self):
        """Large evidence must not overflow context window."""
        huge_chunks = [
            RetrievalResult(
                chunk_id=f"c{i}",
                document_id="doc",
                score=0.5,
                text="x" * 2000,
                company="Co",
                year=2024,
            )
            for i in range(20)
        ]
        messages = build_rag_messages("Question?", huge_chunks)
        # User message must be bounded
        assert len(messages[1]["content"]) < 20_000  # well under 20k

    def test_empty_evidence_returns_messages(self):
        messages = build_rag_messages("Question?", [])
        # Should still return valid messages even with no evidence
        assert len(messages) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Provider construction — build_provider
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildProvider:
    def test_groq_provider_created(self):
        p = build_provider("groq", "llama-3.3-70b", 30, 1024, groq_api_key="test-key")
        assert isinstance(p, GroqProvider)

    def test_openrouter_provider_created(self):
        p = build_provider("openrouter", "gpt-4o", 30, 1024, openrouter_api_key="test-key")
        assert isinstance(p, OpenRouterProvider)

    def test_ollama_provider_created(self):
        p = build_provider("ollama", "mistral", 30, 1024, ollama_base_url="http://localhost:11434")
        assert isinstance(p, OllamaProvider)

    def test_missing_groq_key_raises(self):
        with pytest.raises(ProviderError, match="GROQ_API_KEY"):
            build_provider("groq", "llama-3", 30, 1024)

    def test_missing_openrouter_key_raises(self):
        with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
            build_provider("openrouter", "gpt-4o", 30, 1024)

    def test_unknown_provider_raises(self):
        with pytest.raises(ProviderError, match="Unknown LLM provider"):
            build_provider("unknown_llm", "model", 30, 1024, groq_api_key="key")
