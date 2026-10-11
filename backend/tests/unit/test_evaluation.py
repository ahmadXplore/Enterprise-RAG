"""Unit tests for Evaluation dataset, IR metrics, and benchmark runner."""
from pathlib import Path

import pytest

from packages.evaluation.dataset import (
    EvaluationCase,
    get_curated_benchmark_cases,
    load_benchmark_dataset,
    save_benchmark_dataset,
)
from packages.evaluation.metrics import mrr, ndcg_at_k, recall_at_k
from packages.evaluation.runner import BenchmarkRunner
from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import DeterministicMockEmbedder
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.qdrant_client import create_qdrant_client, ensure_collection
from packages.retrieval.reranker import LexicalSemanticMockReranker
from packages.retrieval.sparse import SparseRetriever


class TestMetrics:
    def test_recall_at_k(self):
        retrieved = ["c1", "c2", "c3", "c4", "c5"]
        expected = ["c2", "c5", "c9"]  # 2 out of 3 retrieved

        assert pytest.approx(recall_at_k(retrieved, expected, k=5), rel=1e-3) == 2.0 / 3.0
        assert recall_at_k(retrieved, expected, k=1) == 0.0
        assert pytest.approx(recall_at_k(retrieved, expected, k=2), rel=1e-3) == 1.0 / 3.0

    def test_recall_at_k_unanswerable(self):
        # When expected is empty, recall is 1.0
        assert recall_at_k(["c1", "c2"], [], k=5) == 1.0

    def test_mrr(self):
        retrieved = ["c1", "c2", "c3"]
        assert mrr(retrieved, ["c1"]) == 1.0  # rank 1
        assert mrr(retrieved, ["c2"]) == 0.5  # rank 2
        assert pytest.approx(mrr(retrieved, ["c3"]), rel=1e-3) == 1.0 / 3.0
        assert mrr(retrieved, ["c99"]) == 0.0  # not found

    def test_ndcg_at_k(self):
        # Perfect ranking: highest grade first
        retrieved_perfect = ["c1", "c2", "c3"]
        grades = {"c1": 3, "c2": 2, "c3": 1}
        assert pytest.approx(ndcg_at_k(retrieved_perfect, grades, k=3), rel=1e-3) == 1.0

        # Sub-optimal ranking: lowest grade first
        retrieved_suboptimal = ["c3", "c2", "c1"]
        score = ndcg_at_k(retrieved_suboptimal, grades, k=3)
        assert score < 1.0
        assert score > 0.0

        # Empty grades
        assert ndcg_at_k(["c1"], {}, k=3) == 1.0


class TestEvaluationDataset:
    def test_category_counts(self):
        cases = get_curated_benchmark_cases()
        assert len(cases) == 110

        counts: dict[str, int] = {}
        for c in cases:
            counts[c.query_type] = counts.get(c.query_type, 0) + 1

        assert counts["direct_lookup"] == 20
        assert counts["temporal"] == 20
        assert counts["comparison"] == 20
        assert counts["numerical"] == 15
        assert counts["legal"] == 15
        assert counts["cross_document"] == 10
        assert counts["unanswerable"] == 10

    def test_case_schema_validity(self):
        cases = get_curated_benchmark_cases()
        for case in cases:
            assert case.id
            assert case.question
            assert case.query_type
            if case.query_type == "unanswerable":
                assert len(case.expected_chunk_ids) == 0
            else:
                assert len(case.expected_chunk_ids) > 0

    def test_dataset_save_and_load(self, tmp_path: Path):
        file_path = tmp_path / "test_dataset.json"
        cases = get_curated_benchmark_cases()[:5]
        save_benchmark_dataset(cases, file_path)
        loaded = load_benchmark_dataset(file_path)
        assert len(loaded) == 5
        assert loaded[0].id == cases[0].id


class TestBenchmarkRunner:
    def test_benchmark_runner_execution(self, tmp_path: Path):
        client = create_qdrant_client(in_memory=True)
        ensure_collection(client, collection_name="eval_test_col", dense_dim=384, recreate=True)

        embedder = DeterministicMockEmbedder(dimension=384)
        dense = DenseRetriever(client=client, embedder=embedder, collection_name="eval_test_col")
        sparse = SparseRetriever(client=client, embedder=embedder, collection_name="eval_test_col")
        hybrid = HybridRetriever(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=LexicalSemanticMockReranker(),
        )

        runner = BenchmarkRunner(
            dense_retriever=dense,
            sparse_retriever=sparse,
            hybrid_retriever=hybrid,
        )

        sample_cases = [
            EvaluationCase(
                id="t1",
                question="What is Apple's CIK?",
                query_type="direct_lookup",
                expected_chunk_ids=["chunk-1"],
                relevance_grades={"chunk-1": 3},
            ),
            EvaluationCase(
                id="t2",
                question="Unanswerable question",
                query_type="unanswerable",
                expected_chunk_ids=[],
                relevance_grades={},
            ),
        ]

        results = runner.run_benchmark(sample_cases)
        assert "dense_only" in results
        assert "sparse_only" in results
        assert "hybrid" in results
        assert "hybrid_rerank" in results

        # Test reports generation
        json_path = tmp_path / "report.json"
        md_path = tmp_path / "report.md"
        runner.save_reports(results, json_output_path=json_path, md_output_path=md_path)

        assert json_path.exists()
        assert md_path.exists()
        assert len(md_path.read_text(encoding="utf-8")) > 100
