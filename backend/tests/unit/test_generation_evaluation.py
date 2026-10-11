"""Unit tests for Phase 12 generation evaluation metrics and comparative runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.evaluation.dataset import EvaluationCase
from packages.evaluation.generation_eval import GenerationEvaluationRunner
from packages.evaluation.metrics import (
    abstention_correctness,
    answer_relevance,
    citation_accuracy,
    citation_completeness,
    groundedness,
)
from packages.llm.generation import GenerationResult
from packages.retrieval.models import RetrievalResult


class TestGenerationMetrics:
    def test_answer_relevance_perfect(self):
        gen = "Apple's CIK number is 0000320193."
        exp = "0000320193"
        score = answer_relevance(gen, exp, "What is Apple's CIK?")
        assert score > 0.0

    def test_answer_relevance_empty(self):
        assert answer_relevance("", "expected", "query") == 0.0
        assert answer_relevance("   ", "expected", "query") == 0.0

    def test_groundedness_supported(self):
        evidence = ["Apple Inc. reported fiscal year 2024 total revenue of 391 billion dollars."]
        answer = "Apple reported 2024 revenue of 391 billion."
        score = groundedness(answer, evidence)
        assert score >= 0.7  # most content tokens supported

    def test_groundedness_unsupported(self):
        evidence = ["Banana Corp makes fruit salads."]
        answer = "Rocket propulsion uses liquid hydrogen and oxygen oxidizer."
        score = groundedness(answer, evidence)
        assert score == 0.0

    def test_groundedness_empty_evidence(self):
        answer = "Something here"
        assert groundedness(answer, []) == 0.0

    def test_citation_accuracy(self):
        # 2 cited, both in expected
        assert citation_accuracy(["c1", "c2"], ["c1", "c2", "c3"]) == 1.0
        # 2 cited, 1 in expected
        assert citation_accuracy(["c1", "c99"], ["c1", "c2"]) == 0.5
        # None cited, none expected
        assert citation_accuracy([], []) == 1.0
        # Cited something when none expected (unanswerable)
        assert citation_accuracy(["c1"], []) == 0.0

    def test_citation_completeness(self):
        assert citation_completeness(["c1", "c2"], ["c1", "c2", "c3"]) == pytest.approx(
            2.0 / 3.0, 0.01
        )
        # All expected cited
        assert citation_completeness(["c1", "c2", "c3", "c4"], ["c1", "c2"]) == 1.0
        # None expected
        assert citation_completeness([], []) == 1.0
        # None cited when some expected
        assert citation_completeness([], ["c1"]) == 0.0

    def test_abstention_correctness(self):
        assert abstention_correctness(abstained=True, is_unanswerable=True) is True
        assert abstention_correctness(abstained=False, is_unanswerable=False) is True
        assert abstention_correctness(abstained=True, is_unanswerable=False) is False
        assert abstention_correctness(abstained=False, is_unanswerable=True) is False


class TestGenerationEvaluationRunner:
    @pytest.mark.asyncio
    async def test_comparative_runner_execution(self, tmp_path: Path):
        mock_generator = MagicMock()
        mock_generator.generate = AsyncMock(
            return_value=GenerationResult(
                answer="Apple CIK is 0000320193.",
                citation_ids=["chunk-1"],
                grounded=True,
                abstained=False,
                query_type="DIRECT",
            )
        )

        chunk = RetrievalResult(
            chunk_id="chunk-1",
            document_id="doc-1",
            text="Apple CIK is 0000320193.",
            score=0.9,
            metadata={"company": "Apple Inc."},
        )

        mock_no_rerank = MagicMock()
        mock_no_rerank.retrieve.return_value = ([chunk], MagicMock())

        mock_rerank = MagicMock()
        mock_rerank.retrieve.return_value = ([chunk], MagicMock())

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(
            return_value=GenerationResult(
                answer="Apple CIK is 0000320193.",
                citation_ids=["chunk-1"],
                grounded=True,
                abstained=False,
                query_type="DIRECT",
            )
        )

        runner = GenerationEvaluationRunner(
            generator=mock_generator,
            hybrid_retriever_no_rerank=mock_no_rerank,
            hybrid_retriever_rerank=mock_rerank,
            agentic_graph=mock_agent,
        )

        cases = [
            EvaluationCase(
                id="case-1",
                question="What is Apple's CIK?",
                query_type="direct_lookup",
                expected_chunk_ids=["chunk-1"],
                expected_answer="0000320193",
            ),
            EvaluationCase(
                id="case-2",
                question="What is unknown?",
                query_type="unanswerable",
                expected_chunk_ids=[],
                expected_answer=None,
            ),
        ]

        summaries = await runner.run_comparative_benchmark(cases)
        assert "no_reranker" in summaries
        assert "reranker" in summaries
        assert "agentic_retrieval" in summaries

        s = summaries["no_reranker"]
        assert s.total_cases == 2
        assert s.mean_answer_relevance > 0.0

        # Test report saving
        json_file = tmp_path / "eval.json"
        md_file = tmp_path / "eval.md"
        runner.save_reports(summaries, json_file, md_file)
        assert json_file.exists()
        assert md_file.exists()
        content = md_file.read_text(encoding="utf-8")
        assert "Phase 12: Generation & Grounding Evaluation Report" in content
        assert "no_reranker" in content
        assert "reranker" in content
        assert "agentic_retrieval" in content
