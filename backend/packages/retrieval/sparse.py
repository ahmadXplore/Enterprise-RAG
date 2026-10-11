"""Sparse BM25 vector retriever using Qdrant vector database."""
from typing import Any

from qdrant_client import QdrantClient, models

from packages.retrieval.embeddings import SparseEmbedder
from packages.retrieval.indexer import build_metadata_filter
from packages.retrieval.models import RetrievalResult
from packages.retrieval.qdrant_client import DEFAULT_COLLECTION


class SparseRetriever:
    """Retrieve top-K candidates using sparse BM25 token representations."""

    def __init__(
        self,
        client: QdrantClient,
        embedder: SparseEmbedder,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.client = client
        self.embedder = embedder
        self.collection_name = collection_name

    def retrieve(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 30,
    ) -> list[RetrievalResult]:
        """Execute sparse BM25 similarity search in Qdrant.

        Args:
            query: User search query string.
            filters: Optional metadata filters.
            top_k: Number of candidates to retrieve.

        Returns:
            List of RetrievalResult objects ordered by descending score.
        """
        if not query.strip() or top_k <= 0:
            return []

        indices, values = self.embedder.embed_query_sparse(query)
        if not indices:
            return []

        query_sparse = models.SparseVector(indices=indices, values=values)
        qdrant_filter = build_metadata_filter(filters)

        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_sparse,
            using="sparse",
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
        )

        results: list[RetrievalResult] = []
        for rank, point in enumerate(search_result.points, start=1):
            payload = point.payload or {}
            results.append(
                RetrievalResult(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    document_id=str(payload.get("document_id", "")),
                    score=float(point.score),
                    text=str(payload.get("text", "")),
                    company=str(payload.get("company", "")),
                    year=int(payload.get("year", 0)),
                    document_type=str(payload.get("document_type", "")),
                    section=str(payload.get("section", "")),
                    page_start=payload.get("page_start"),
                    page_end=payload.get("page_end"),
                    chunk_type=payload.get("chunk_type"),
                    rank=rank,
                    metadata=payload,
                )
            )

        return results
