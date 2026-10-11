"""Reciprocal Rank Fusion (RRF) for combining multiple ranked retrieval candidate lists."""
from packages.retrieval.models import RetrievalResult


class ReciprocalRankFusion:
    """Combines dense and sparse ranked retrieval lists using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_Score(d) = sum(1 / (k + rank_i(d))) for all lists i containing d.
    """

    def __init__(self, k: int = 60) -> None:
        if k <= 0:
            raise ValueError("RRF constant k must be > 0")
        self.k = k

    def fuse(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
        fusion_k: int = 20,
    ) -> list[RetrievalResult]:
        """Fuse two candidate lists and return the top fusion_k ranked items.

        Args:
            dense_results: Candidates from dense retriever.
            sparse_results: Candidates from sparse retriever.
            fusion_k: Maximum number of fused items to return.

        Returns:
            List of RetrievalResult objects sorted by descending RRF score.
        """
        scores: dict[str, float] = {}
        items: dict[str, RetrievalResult] = {}
        dense_ranks: dict[str, int] = {}
        sparse_ranks: dict[str, int] = {}

        for rank, res in enumerate(dense_results, start=1):
            scores[res.chunk_id] = scores.get(res.chunk_id, 0.0) + (1.0 / (self.k + rank))
            dense_ranks[res.chunk_id] = rank
            if res.chunk_id not in items:
                items[res.chunk_id] = res

        for rank, res in enumerate(sparse_results, start=1):
            scores[res.chunk_id] = scores.get(res.chunk_id, 0.0) + (1.0 / (self.k + rank))
            sparse_ranks[res.chunk_id] = rank
            if res.chunk_id not in items:
                items[res.chunk_id] = res

        # Sort items by fused RRF score descending
        sorted_chunk_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

        fused_results: list[RetrievalResult] = []
        for new_rank, chunk_id in enumerate(sorted_chunk_ids[:fusion_k], start=1):
            base_item = items[chunk_id]
            fused_score = scores[chunk_id]

            meta = dict(base_item.metadata)
            meta["dense_rank"] = dense_ranks.get(chunk_id)
            meta["sparse_rank"] = sparse_ranks.get(chunk_id)
            meta["rrf_score"] = fused_score

            fused_results.append(
                RetrievalResult(
                    chunk_id=base_item.chunk_id,
                    document_id=base_item.document_id,
                    score=fused_score,
                    text=base_item.text,
                    company=base_item.company,
                    year=base_item.year,
                    document_type=base_item.document_type,
                    section=base_item.section,
                    page_start=base_item.page_start,
                    page_end=base_item.page_end,
                    chunk_type=base_item.chunk_type,
                    rank=new_rank,
                    metadata=meta,
                )
            )

        return fused_results
