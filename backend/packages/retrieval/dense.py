"""Dense vector retriever using Qdrant vector database."""
from typing import Any

from qdrant_client import QdrantClient

from packages.retrieval.embeddings import DenseEmbedder
from packages.retrieval.indexer import build_metadata_filter
from packages.retrieval.models import RetrievalResult
from packages.retrieval.qdrant_client import DEFAULT_COLLECTION


class DenseRetriever:
    """Retrieve top-K candidates using dense semantic embeddings."""

    def __init__(
        self,
        client: QdrantClient,
        embedder: DenseEmbedder,
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
        """Execute dense vector similarity search in Qdrant.

        Args:
            query: User search query string.
            filters: Optional metadata filters.
            top_k: Number of candidates to retrieve.

        Returns:
            List of RetrievalResult objects ordered by descending score.
        """
        if not query.strip() or top_k <= 0:
            return []

        query_vector = self.embedder.embed_query(query)
        qdrant_filter = build_metadata_filter(filters)

        search_result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using="dense",
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
