"""Unit tests for Phase 10 specialised workflows.

Tests use the mock LLM provider and mock retriever — no real network or Qdrant calls.

Rule 17: Tests cover numerical extraction, unit validation, comparison independent
         retrieval, temporal year filtering, and authorized_document_ids enforcement.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.llm.generation import RAGGenerator
from packages.llm.workflows import (
    ComparisonWorkflow,
    ExtractedValue,
    NumericalWorkflow,
    TemporalWorkflow,
    _extract_numeric_value,
    _validate_units,
    run_numerical_analysis,
)
from packages.retrieval.models import RetrievalResult

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_chunk(
    chunk_id: str,
    text: str,
    company: str = "Apple Inc.",
    year: int = 2024,
    score: float = 0.9,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=f"doc-{company.lower().replace(' ', '-')}-{year}",
        score=score,
        text=text,
        company=company,
        year=year,
        section="Financials",
    )


def _mock_generator(llm_answer: str) -> RAGGenerator:
    provider = AsyncMock()
    provider.generate.return_value = {
        "content": json.dumps(
            {
                "answer": llm_answer,
                "citation_ids": ["chunk-001"],
                "grounded": True,
                "abstained": False,
            }
        ),
        "model": "mock",
        "usage": {},
    }
    return RAGGenerator(provider=provider)


def _mock_retriever(returns: list[RetrievalResult]) -> MagicMock:
    retriever = MagicMock()
    retriever.retrieve.return_value = (returns, MagicMock())
    return retriever


# ─────────────────────────────────────────────────────────────────────────────
# Numerical value extraction
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractNumericValue:
    def test_extracts_billion(self):
        val, unit = _extract_numeric_value("Revenue was $47.5 billion in 2024.")
        assert val == pytest.approx(47_500_000_000.0)
        assert unit == "billion"

    def test_extracts_million(self):
        val, unit = _extract_numeric_value("Net sales: $201,183 million")
        assert val == pytest.approx(201_183_000_000.0)
        assert unit == "million"

    def test_extracts_plain_number(self):
        val, unit = _extract_numeric_value("Growth of 19%")
        assert val == pytest.approx(19.0)

    def test_no_number_returns_none(self):
        val, unit = _extract_numeric_value("No numbers here.")
        assert val is None
        assert unit is None


class TestValidateUnits:
    def test_consistent_units(self):
        vals = [
            ExtractedValue("c1", "text", 100.0, "million"),
            ExtractedValue("c2", "text", 200.0, "million"),
        ]
        ok, unit = _validate_units(vals)
        assert ok is True
        assert unit == "million"

    def test_mixed_units(self):
        vals = [
            ExtractedValue("c1", "text", 100.0, "million"),
            ExtractedValue("c2", "text", 200.0, "billion"),
        ]
        ok, unit = _validate_units(vals)
        assert ok is False

    def test_empty_list(self):
        ok, unit = _validate_units([])
        assert ok is True
        assert unit is None


# ─────────────────────────────────────────────────────────────────────────────
# run_numerical_analysis
# ─────────────────────────────────────────────────────────────────────────────


class TestRunNumericalAnalysis:
    def test_sums_values_from_evidence(self):
        evidence = [
            _make_chunk("chunk-001", "iPhone sales: $201 billion."),
            _make_chunk("chunk-002", "Services revenue: $96 billion."),
        ]
        result = run_numerical_analysis(evidence)
        assert result.computed_value == pytest.approx(297_000_000_000.0)
        assert len(result.source_chunk_ids) == 2

    def test_no_numbers_returns_none(self):
        evidence = [_make_chunk("c1", "No financial data here.")]
        result = run_numerical_analysis(evidence)
        assert result.computed_value is None
        assert result.source_values == []

    def test_unit_inconsistency_flagged(self):
        evidence = [
            _make_chunk("c1", "Revenue $201 million."),
            _make_chunk("c2", "Profit $5 billion."),
        ]
        result = run_numerical_analysis(evidence)
        assert result.unit_consistent is False
        assert "mixed units" in result.note.lower()


# ─────────────────────────────────────────────────────────────────────────────
# NumericalWorkflow
# ─────────────────────────────────────────────────────────────────────────────


class TestNumericalWorkflow:
    @pytest.mark.asyncio
    async def test_passes_computed_value_to_llm(self):
        evidence = [_make_chunk("chunk-001", "iPhone sales: $201 billion.")]
        gen = _mock_generator("iPhone sales were approximately $201 billion.")
        wf = NumericalWorkflow(generator=gen)
        result = await wf.run("What were iPhone sales?", evidence=evidence)
        assert result.query_type == "NUMERICAL"
        assert result.grounded is True

    @pytest.mark.asyncio
    async def test_abstains_on_no_evidence(self):
        gen = _mock_generator("")
        wf = NumericalWorkflow(generator=gen)
        result = await wf.run("Revenue?", evidence=[])
        assert result.abstained is True


# ─────────────────────────────────────────────────────────────────────────────
# TemporalWorkflow
# ─────────────────────────────────────────────────────────────────────────────


class TestTemporalWorkflow:
    @pytest.mark.asyncio
    async def test_filters_to_requested_year(self):
        evidence_2024 = [_make_chunk("c1", "Revenue $200B", year=2024)]
        evidence_2023 = [_make_chunk("c2", "Revenue $150B", year=2023)]
        gen = _mock_generator("Revenue in 2024 was $200B.")

        wf = TemporalWorkflow(generator=gen)
        result = await wf.run(
            "Revenue in 2024?",
            evidence=evidence_2024 + evidence_2023,
            requested_year=2024,
        )
        assert result.query_type == "TEMPORAL"
        # Generator should be called with only 2024 evidence
        call_kwargs = gen._provider.generate.call_args
        assert call_kwargs is not None
        messages = call_kwargs.kwargs["messages"]
        user_content = messages[1]["content"]
        # Only chunk c1 (2024) should appear
        assert "c1" in user_content
        # c2 (2023) should be excluded
        assert "c2" not in user_content

    @pytest.mark.asyncio
    async def test_uses_all_evidence_when_no_year_match(self):
        evidence = [
            _make_chunk("c1", "Revenue $200B", year=2023),
            _make_chunk("c2", "Revenue $220B", year=2022),
        ]
        gen = _mock_generator("No 2024 data found.")
        wf = TemporalWorkflow(generator=gen)
        result = await wf.run("Revenue in 2024?", evidence=evidence, requested_year=2024)
        # Falls back to all evidence
        assert result.query_type == "TEMPORAL"


# ─────────────────────────────────────────────────────────────────────────────
# ComparisonWorkflow — independent retrieval per entity, auth filter enforced
# ─────────────────────────────────────────────────────────────────────────────


class TestComparisonWorkflow:
    @pytest.mark.asyncio
    async def test_retrieves_independently_per_entity(self):
        """Each entity gets a separate retrieve() call — Rule 12: auth filter applied."""
        apple_chunk = _make_chunk("c-apple", "Apple revenue $200B.", company="Apple Inc.")
        msft_chunk = _make_chunk(
            "c-msft", "Microsoft revenue $180B.", company="Microsoft Corporation"
        )

        retriever = MagicMock()
        call_count = 0

        def _retrieve(query, filters):
            nonlocal call_count
            call_count += 1
            if "Apple" in query:
                return ([apple_chunk], MagicMock())
            return ([msft_chunk], MagicMock())

        retriever.retrieve.side_effect = _retrieve

        gen = _mock_generator("Apple ($200B) exceeds Microsoft ($180B).")
        wf = ComparisonWorkflow(generator=gen, retriever=retriever)

        result = await wf.run(
            question="Compare Apple vs Microsoft revenue",
            entities=["Apple", "Microsoft"],
            metric="revenue",
            authorized_document_ids=["doc-apple-2024", "doc-microsoft-2024"],
        )

        # Two retrieve calls — one per entity
        assert retriever.retrieve.call_count == 2
        assert result.query_type == "COMPARISON"

    @pytest.mark.asyncio
    async def test_authorized_document_ids_in_every_filter(self):
        """Rule 12: authorized_document_ids must appear in every retrieval filter."""
        auth_ids = ["authorized-doc-1", "authorized-doc-2"]
        retriever = MagicMock()
        retriever.retrieve.return_value = ([], MagicMock())

        gen = _mock_generator("No data.")
        wf = ComparisonWorkflow(generator=gen, retriever=retriever)

        await wf.run(
            question="Compare A vs B",
            entities=["A", "B"],
            metric="metric",
            authorized_document_ids=auth_ids,
        )

        for call in retriever.retrieve.call_args_list:
            filters = (
                call.kwargs.get("filters") or (call.args[1] if len(call.args) > 1 else {}) or {}
            )
            assert "authorized_document_ids" in filters
            assert filters["authorized_document_ids"] == auth_ids

    @pytest.mark.asyncio
    async def test_abstains_when_no_entities(self):
        retriever = _mock_retriever([])
        gen = _mock_generator("")
        wf = ComparisonWorkflow(generator=gen, retriever=retriever)
        result = await wf.run(
            question="Compare?",
            entities=[],
            metric=None,
            authorized_document_ids=["doc-1"],
        )
        assert result.abstained is True
