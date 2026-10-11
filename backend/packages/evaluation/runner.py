"""Benchmark evaluation runner comparing Dense, Sparse, Hybrid, and Hybrid+Reranker."""
import json
import time
from pathlib import Path
from typing import Any

from packages.evaluation.dataset import EvaluationCase
from packages.evaluation.metrics import mrr, ndcg_at_k, recall_at_k
from packages.retrieval.dense import DenseRetriever
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.models import RetrievalConfig, RetrievalResult
from packages.retrieval.sparse import SparseRetriever


class BenchmarkRunner:
    """Executes benchmark evaluation across multiple retrieval pipeline configurations."""

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        hybrid_retriever: HybridRetriever,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.hybrid_retriever = hybrid_retriever

    def evaluate_pipeline(
        self,
        pipeline_name: str,
        cases: list[EvaluationCase],
        retrieve_fn: Any,
    ) -> dict[str, Any]:
        """Evaluate a single pipeline over all test cases."""
        recalls_5: list[float] = []
        recalls_10: list[float] = []
        mrrs: list[float] = []
        ndcgs_5: list[float] = []
        ndcgs_10: list[float] = []
        latencies_ms: list[float] = []

        by_category: dict[str, dict[str, list[float]]] = {}

        for case in cases:
            q_type = case.query_type
            if q_type not in by_category:
                by_category[q_type] = {
                    "recall_5": [],
                    "recall_10": [],
                    "mrr": [],
                    "ndcg_5": [],
                    "ndcg_10": [],
                }

            filters = case.metadata_constraints or None

            t0 = time.perf_counter()
            results: list[RetrievalResult] = retrieve_fn(case.question, filters)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(elapsed_ms)

            retrieved_ids = [r.chunk_id for r in results]

            r5 = recall_at_k(retrieved_ids, case.expected_chunk_ids, k=5)
            r10 = recall_at_k(retrieved_ids, case.expected_chunk_ids, k=10)
            m = mrr(retrieved_ids, case.expected_chunk_ids)
            n5 = ndcg_at_k(retrieved_ids, case.relevance_grades, k=5)
            n10 = ndcg_at_k(retrieved_ids, case.relevance_grades, k=10)

            recalls_5.append(r5)
            recalls_10.append(r10)
            mrrs.append(m)
            ndcgs_5.append(n5)
            ndcgs_10.append(n10)

            by_category[q_type]["recall_5"].append(r5)
            by_category[q_type]["recall_10"].append(r10)
            by_category[q_type]["mrr"].append(m)
            by_category[q_type]["ndcg_5"].append(n5)
            by_category[q_type]["ndcg_10"].append(n10)

        n = max(len(cases), 1)
        category_summary: dict[str, dict[str, float]] = {}
        for cat, metric_lists in by_category.items():
            cn = max(len(metric_lists["recall_10"]), 1)
            category_summary[cat] = {
                "count": len(metric_lists["recall_10"]),
                "recall_at_5": sum(metric_lists["recall_5"]) / cn,
                "recall_at_10": sum(metric_lists["recall_10"]) / cn,
                "mrr": sum(metric_lists["mrr"]) / cn,
                "ndcg_at_5": sum(metric_lists["ndcg_5"]) / cn,
                "ndcg_at_10": sum(metric_lists["ndcg_10"]) / cn,
            }

        return {
            "pipeline": pipeline_name,
            "total_cases": len(cases),
            "recall_at_5": sum(recalls_5) / n,
            "recall_at_10": sum(recalls_10) / n,
            "mrr": sum(mrrs) / n,
            "ndcg_at_5": sum(ndcgs_5) / n,
            "ndcg_at_10": sum(ndcgs_10) / n,
            "avg_latency_ms": sum(latencies_ms) / n,
            "by_category": category_summary,
        }

    def run_benchmark(self, cases: list[EvaluationCase]) -> dict[str, Any]:
        """Compare all four retrieval configurations:
        1. Dense only
        2. Sparse only
        3. Hybrid (Dense + Sparse + RRF)
        4. Hybrid + Reranker
        """
        # 1. Dense only
        def retrieve_dense(q: str, f: dict | None) -> list[RetrievalResult]:
            return self.dense_retriever.retrieve(query=q, filters=f, top_k=10)

        # 2. Sparse only
        def retrieve_sparse(q: str, f: dict | None) -> list[RetrievalResult]:
            return self.sparse_retriever.retrieve(query=q, filters=f, top_k=10)

        # 3. Hybrid without reranker (RRF top 10)
        no_rerank_cfg = RetrievalConfig(dense_k=30, sparse_k=30, fusion_k=10, rerank_k=10)

        def retrieve_hybrid(q: str, f: dict | None) -> list[RetrievalResult]:
            original_reranker = self.hybrid_retriever.reranker
            self.hybrid_retriever.reranker = None
            try:
                res, _ = self.hybrid_retriever.retrieve(
                    query=q, filters=f, config_override=no_rerank_cfg
                )
                return res
            finally:
                self.hybrid_retriever.reranker = original_reranker

        # 4. Hybrid with reranker (RRF 20 -> Reranker 10)
        def retrieve_hybrid_rerank(q: str, f: dict | None) -> list[RetrievalResult]:
            res, _ = self.hybrid_retriever.retrieve(query=q, filters=f)
            return res

        results: dict[str, Any] = {
            "dense_only": self.evaluate_pipeline("Dense only", cases, retrieve_dense),
            "sparse_only": self.evaluate_pipeline("Sparse only", cases, retrieve_sparse),
            "hybrid": self.evaluate_pipeline(
                "Hybrid (Dense + Sparse + RRF)", cases, retrieve_hybrid
            ),
            "hybrid_rerank": self.evaluate_pipeline(
                "Hybrid + Reranker", cases, retrieve_hybrid_rerank
            ),
        }

        return results

    @staticmethod
    def generate_markdown_report(benchmark_results: dict[str, Any]) -> str:
        """Generate human-readable Markdown evaluation report."""
        lines = [
            "# Retrieval Engine Benchmark Report",
            "",
            "## 1. Overall Pipeline Comparison",
            "",
            "| Pipeline | Recall@5 | Recall@10 | MRR | nDCG@5 | nDCG@10 | Avg Latency (ms) |",
            "|---|---|---|---|---|---|---|",
        ]

        for _, data in benchmark_results.items():
            lines.append(
                f"| **{data['pipeline']}** | {data['recall_at_5']:.4f} | "
                f"{data['recall_at_10']:.4f} | {data['mrr']:.4f} | "
                f"{data['ndcg_at_5']:.4f} | {data['ndcg_at_10']:.4f} | "
                f"{data['avg_latency_ms']:.2f} |"
            )

        lines.extend([
            "",
            "## 2. Performance by Query Category (Hybrid + Reranker)",
            "",
            "| Category | Cases | Recall@5 | Recall@10 | MRR | nDCG@5 | nDCG@10 |",
            "|---|---|---|---|---|---|---|",
        ])

        hybrid_data = benchmark_results.get("hybrid_rerank", {})
        categories = hybrid_data.get("by_category", {})
        for cat, cdata in categories.items():
            lines.append(
                f"| `{cat}` | {cdata['count']} | {cdata['recall_at_5']:.4f} | "
                f"{cdata['recall_at_10']:.4f} | {cdata['mrr']:.4f} | "
                f"{cdata['ndcg_at_5']:.4f} | {cdata['ndcg_at_10']:.4f} |"
            )

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def save_reports(
        benchmark_results: dict[str, Any],
        json_output_path: Path,
        md_output_path: Path,
    ) -> None:
        """Save both machine-readable JSON and human-readable Markdown reports."""
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_output_path, "w", encoding="utf-8") as f:
            json.dump(benchmark_results, f, indent=2)

        md_content = BenchmarkRunner.generate_markdown_report(benchmark_results)
        with open(md_output_path, "w", encoding="utf-8") as f:
            f.write(md_content)
