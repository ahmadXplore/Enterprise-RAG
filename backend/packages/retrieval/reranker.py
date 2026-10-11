"""Cross-encoder reranking service for candidate refinement."""
from typing import Protocol

from packages.retrieval.models import RetrievalResult

try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    _FASTEMBED_RERANK_AVAILABLE = True
except ImportError:
    _FASTEMBED_RERANK_AVAILABLE = False


class Reranker(Protocol):
    """Protocol for cross-encoder rerankers."""

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]: ...


class FastEmbedReranker:
    """Reranker using FastEmbed cross-encoder model (e.g. ms-marco-MiniLM-L-6-v2)."""

    def __init__(self, model_name: str = "Xenova/ms-marco-MiniLM-L-6-v2") -> None:
        if not _FASTEMBED_RERANK_AVAILABLE:
            raise RuntimeError("fastembed cross-encoder is required for FastEmbedReranker")
        self.model_name = model_name
        self._model = TextCrossEncoder(model_name=model_name)

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        if not candidates or top_k <= 0:
            return []

        texts = [c.text for c in candidates]
        raw_scores = list(self._model.rerank(query, texts))

        import math

        def calibrate_score(raw_logit: float) -> float:
            """Calibrate cross-encoder logit (typical range -8.0 to +6.0) into [0.05, 0.99] probability."""
            try:
                # Center around -2.5 with temperature 2.0
                scaled = (raw_logit + 2.5) / 2.0
                prob = 1.0 / (1.0 + math.exp(-scaled))
                return max(0.01, min(0.99, prob))
            except OverflowError:
                return 0.01 if raw_logit < 0 else 0.99

        # Pair each candidate with its calibrated probability and raw logit
        scored_pairs: list[tuple[float, float, RetrievalResult]] = []
        for raw_s, candidate in zip(raw_scores, candidates, strict=True):
            raw_float = float(raw_s)
            calibrated_prob = calibrate_score(raw_float)
            scored_pairs.append((calibrated_prob, raw_float, candidate))

        scored_pairs.sort(key=lambda pair: pair[0], reverse=True)

        reranked_results: list[RetrievalResult] = []
        for rank, (calibrated_score, raw_score, candidate) in enumerate(scored_pairs[:top_k], start=1):
            meta = dict(candidate.metadata)
            meta["raw_rerank_logit"] = raw_score
            meta["rerank_score"] = calibrated_score
            reranked_results.append(
                RetrievalResult(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    score=calibrated_score,
                    text=candidate.text,
                    company=candidate.company,
                    year=candidate.year,
                    document_type=candidate.document_type,
                    section=candidate.section,
                    page_start=candidate.page_start,
                    page_end=candidate.page_end,
                    chunk_type=candidate.chunk_type,
                    rank=rank,
                    metadata=meta,
                )
            )

        return reranked_results


class LexicalSemanticMockReranker:
    """Deterministic, lightweight reranker for fast unit tests without network/ONNX."""

    def rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        if not candidates or top_k <= 0:
            return []

        query_words = set(query.lower().split())

        scored_pairs: list[tuple[float, RetrievalResult]] = []
        for candidate in candidates:
            cand_words = candidate.text.lower().split()
            if not cand_words:
                overlap = 0.0
            else:
                overlap = sum(1 for w in cand_words if w in query_words) / len(cand_words)
            # Combine initial candidate score + word overlap
            combined_score = candidate.score * 0.5 + overlap * 0.5
            scored_pairs.append((combined_score, candidate))

        scored_pairs.sort(key=lambda pair: pair[0], reverse=True)

        results: list[RetrievalResult] = []
        for rank, (score, candidate) in enumerate(scored_pairs[:top_k], start=1):
            meta = dict(candidate.metadata)
            meta["rerank_score"] = score
            results.append(
                RetrievalResult(
                    chunk_id=candidate.chunk_id,
                    document_id=candidate.document_id,
                    score=score,
                    text=candidate.text,
                    company=candidate.company,
                    year=candidate.year,
                    document_type=candidate.document_type,
                    section=candidate.section,
                    page_start=candidate.page_start,
                    page_end=candidate.page_end,
                    chunk_type=candidate.chunk_type,
                    rank=rank,
                    metadata=meta,
                )
            )

        return results
