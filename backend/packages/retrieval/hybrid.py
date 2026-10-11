"""Hybrid retriever orchestrating Dense, Sparse (BM25), RRF, and Reranking."""
import time
from typing import Any

from packages.retrieval.dense import DenseRetriever
from packages.retrieval.fusion import ReciprocalRankFusion
from packages.retrieval.models import RetrievalConfig, RetrievalDiagnostics, RetrievalResult
from packages.retrieval.reranker import Reranker
from packages.retrieval.sparse import SparseRetriever


class HybridRetriever:
    """Modular hybrid retriever coordinating Dense, Sparse, RRF, and Reranking."""

    def __init__(
        self,
        dense_retriever: DenseRetriever,
        sparse_retriever: SparseRetriever,
        reranker: Reranker | None = None,
        fusion: ReciprocalRankFusion | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.dense_retriever = dense_retriever
        self.sparse_retriever = sparse_retriever
        self.reranker = reranker
        self.config = config or RetrievalConfig()
        self.fusion = fusion or ReciprocalRankFusion(k=self.config.rrf_k)

    def retrieve(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        config_override: RetrievalConfig | None = None,
    ) -> tuple[list[RetrievalResult], RetrievalDiagnostics]:
        """Execute full hybrid retrieval pipeline.

        1. Dense retrieval (top dense_k, default 30)
        2. Sparse BM25 retrieval (top sparse_k, default 30)
        3. RRF fusion (down to fusion_k, default 20)
        4. Cross-encoder reranker (down to rerank_k, default 10)

        Args:
            query: User search query.
            filters: Optional metadata filters.
            config_override: Optional per-query configuration overrides.

        Returns:
            Tuple of (ranked_results, diagnostics).
        """
        cfg = config_override or self.config
        diagnostics = RetrievalDiagnostics()
        start_total = time.perf_counter()

        # Stage 1: Dense Retrieval
        t0 = time.perf_counter()
        dense_results = self.dense_retriever.retrieve(
            query=query,
            filters=filters,
            top_k=cfg.dense_k,
        )
        diagnostics.dense_latency_ms = (time.perf_counter() - t0) * 1000.0
        diagnostics.dense_candidates_count = len(dense_results)

        # Stage 2: Sparse BM25 Retrieval
        t0 = time.perf_counter()
        sparse_results = self.sparse_retriever.retrieve(
            query=query,
            filters=filters,
            top_k=cfg.sparse_k,
        )
        diagnostics.sparse_latency_ms = (time.perf_counter() - t0) * 1000.0
        diagnostics.sparse_candidates_count = len(sparse_results)

        # Stage 3: Reciprocal Rank Fusion (RRF)
        t0 = time.perf_counter()
        fusion_k = cfg.fusion_k
        fused_results = self.fusion.fuse(
            dense_results=dense_results,
            sparse_results=sparse_results,
            fusion_k=fusion_k,
        )
        diagnostics.fusion_latency_ms = (time.perf_counter() - t0) * 1000.0
        diagnostics.fused_candidates_count = len(fused_results)

        # Stage 4: Reranker (if configured)
        if self.reranker and fused_results:
            t0 = time.perf_counter()
            final_results = self.reranker.rerank(
                query=query,
                candidates=fused_results,
                top_k=cfg.rerank_k,
            )
            diagnostics.rerank_latency_ms = (time.perf_counter() - t0) * 1000.0
            diagnostics.reranked_candidates_count = len(final_results)
        else:
            final_results = fused_results[: cfg.rerank_k]
            diagnostics.reranked_candidates_count = len(final_results)

        diagnostics.total_latency_ms = (time.perf_counter() - start_total) * 1000.0
        return final_results, diagnostics
