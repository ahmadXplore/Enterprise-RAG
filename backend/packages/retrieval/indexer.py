"""Idempotent indexing of document chunks into Qdrant vector database."""
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from packages.retrieval.embeddings import DenseEmbedder, SparseEmbedder
from packages.retrieval.qdrant_client import DEFAULT_COLLECTION, ensure_collection


def build_metadata_filter(filters: dict[str, Any] | None) -> models.Filter | None:
    """Build Qdrant Filter from metadata filter dictionary.

    Supports:
        company: str | list[str]
        year: int | list[int]
        document_type: str | list[str]
        document_id: str | list[str]
        section: str
        chunk_type: str | list[str]
        authorized_document_ids: list[str] (Pre-retrieval authorization per Rule 12)
    """
    if not filters:
        return None

    must_conditions: list[models.Condition] = []
    processed_keys: set[str] = set()

    for key, value in filters.items():
        if value is None:
            continue

        if key in ("company", "companies"):
            if "company" in processed_keys:
                continue
            processed_keys.add("company")
            if isinstance(value, list):
                if len(value) == 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="company",
                            match=models.MatchValue(value=str(value[0])),
                        )
                    )
                elif len(value) > 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="company",
                            match=models.MatchAny(any=[str(v) for v in value]),
                        )
                    )
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key="company",
                        match=models.MatchValue(value=str(value)),
                    )
                )

        elif key in ("year", "years"):
            if "year" in processed_keys:
                continue
            processed_keys.add("year")
            if isinstance(value, list):
                if len(value) == 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="year",
                            match=models.MatchValue(value=int(value[0])),
                        )
                    )
                elif len(value) > 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="year",
                            match=models.MatchAny(any=[int(y) for y in value]),
                        )
                    )
            elif isinstance(value, dict):
                # Range filter (gte, lte, gt, lt)
                must_conditions.append(
                    models.FieldCondition(
                        key="year",
                        range=models.Range(**value),
                    )
                )
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key="year",
                        match=models.MatchValue(value=int(value)),
                    )
                )

        elif key in ("document_type", "document_types"):
            if "document_type" in processed_keys:
                continue
            processed_keys.add("document_type")
            if isinstance(value, list):
                if len(value) == 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="document_type",
                            match=models.MatchValue(value=str(value[0])),
                        )
                    )
                elif len(value) > 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key="document_type",
                            match=models.MatchAny(any=[str(v) for v in value]),
                        )
                    )
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key="document_type",
                        match=models.MatchValue(value=str(value)),
                    )
                )

        elif key in ("document_id", "document_ids", "chunk_type", "chunk_types"):
            clean_key = "document_id" if "document_id" in key else "chunk_type"
            if clean_key in processed_keys:
                continue
            processed_keys.add(clean_key)
            if isinstance(value, list):
                if len(value) == 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key=clean_key,
                            match=models.MatchValue(value=str(value[0])),
                        )
                    )
                elif len(value) > 1:
                    must_conditions.append(
                        models.FieldCondition(
                            key=clean_key,
                            match=models.MatchAny(any=[str(v) for v in value]),
                        )
                    )
            else:
                must_conditions.append(
                    models.FieldCondition(
                        key=clean_key,
                        match=models.MatchValue(value=str(value)),
                    )
                )

        elif key == "section":
            must_conditions.append(
                models.FieldCondition(
                    key="section",
                    match=models.MatchText(text=str(value)),
                )
            )

        elif key == "authorized_document_ids":
            # Rule 12: Pre-retrieval authorization scoping
            auth_ids = [str(doc_id) for doc_id in value]
            must_conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=auth_ids),
                )
            )

    if not must_conditions:
        return None

    return models.Filter(must=must_conditions)


class QdrantIndexer:
    """Manages dense and sparse indexing of document chunks into Qdrant."""

    def __init__(
        self,
        client: QdrantClient,
        dense_embedder: DenseEmbedder,
        sparse_embedder: SparseEmbedder,
        collection_name: str = DEFAULT_COLLECTION,
    ) -> None:
        self.client = client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.collection_name = collection_name
        ensure_collection(
            self.client,
            collection_name=self.collection_name,
            dense_dim=self.dense_embedder.dimension,
        )

    def index_chunks(
        self,
        chunks: list[Any],
        document_metadata: dict[str, Any],
        batch_size: int = 64,
    ) -> int:
        """Idempotently index chunks into Qdrant.

        Qdrant point ID equals PostgreSQL document_chunk.id.
        Payload strictly conforms to prompt requirements:
        - chunk_id
        - document_id
        - company
        - year
        - document_type
        - section
        - page_start
        - page_end
        - chunk_type

        Args:
            chunks: List of DocumentChunk models or chunk dicts/objects.
            document_metadata: Dict with document_id, company, year, document_type.
            batch_size: Number of points to upsert per batch.

        Returns:
            Number of points indexed.
        """
        if not chunks:
            return 0

        total_indexed = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [c.text if hasattr(c, "text") else c["text"] for c in batch]

            dense_vectors = self.dense_embedder.embed_texts(texts)
            sparse_vectors = self.sparse_embedder.embed_sparse(texts)

            points: list[models.PointStruct] = []

            for chunk, text, dense_vec, (sparse_indices, sparse_values) in zip(
                batch, texts, dense_vectors, sparse_vectors, strict=True
            ):
                # Ensure Point ID is UUID string matching chunk.id / chunk_id
                raw_id = (
                    getattr(chunk, "id", None)
                    or getattr(chunk, "chunk_id", None)
                    or (
                        chunk.get("id") or chunk.get("chunk_id")
                        if isinstance(chunk, dict)
                        else None
                    )
                )
                if isinstance(raw_id, uuid.UUID):
                    point_id = str(raw_id)
                    stored_chunk_id = str(raw_id)
                elif raw_id:
                    stored_chunk_id = str(raw_id)
                    try:
                        point_id = str(uuid.UUID(str(raw_id)))
                    except ValueError:
                        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(raw_id)))
                else:
                    point_id = str(uuid.uuid4())
                    stored_chunk_id = point_id

                heading_path = getattr(chunk, "heading_path", None)
                if heading_path is None and isinstance(chunk, dict):
                    heading_path = chunk.get("heading_path") or chunk.get("section")

                page_start = getattr(chunk, "page_start", None)
                if page_start is None and isinstance(chunk, dict):
                    page_start = chunk.get("page_start")

                page_end = getattr(chunk, "page_end", None)
                if page_end is None and isinstance(chunk, dict):
                    page_end = chunk.get("page_end")

                chunk_type = getattr(chunk, "chunk_type", None)
                if chunk_type is None and isinstance(chunk, dict):
                    chunk_type = chunk.get("chunk_type")

                token_count = getattr(chunk, "token_count", None)
                if token_count is None and isinstance(chunk, dict):
                    token_count = chunk.get("token_count")

                content_hash = getattr(chunk, "content_hash", None)
                if content_hash is None and isinstance(chunk, dict):
                    content_hash = chunk.get("content_hash")

                try:
                    year_val = int(document_metadata.get("year") or 0)
                except (ValueError, TypeError):
                    year_val = 0

                payload = {
                    "chunk_id": stored_chunk_id,
                    "document_id": str(document_metadata.get("document_id") or ""),
                    "company": str(document_metadata.get("company") or ""),
                    "year": year_val,
                    "document_type": str(document_metadata.get("document_type") or "10-K"),
                    "section": str(heading_path or ""),
                    "page_start": page_start,
                    "page_end": page_end,
                    "chunk_type": chunk_type or "paragraph",
                    "text": text,
                    "token_count": token_count,
                    "content_hash": content_hash,
                }

                point = models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": dense_vec,
                        "sparse": models.SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                    },
                    payload=payload,
                )
                points.append(point)

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            total_indexed += len(points)

        return total_indexed

    def delete_document(self, document_id: str) -> None:
        """Delete all indexed chunks for a document."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=str(document_id)),
                        )
                    ]
                )
            ),
        )

    def reindex_document(
        self,
        document_id: str,
        chunks: list[Any],
        document_metadata: dict[str, Any],
        batch_size: int = 64,
    ) -> int:
        """Re-index all chunks for a document, deleting previous versions first."""
        self.delete_document(document_id=document_id)
        metadata = dict(document_metadata)
        metadata["document_id"] = document_id
        return self.index_chunks(chunks=chunks, document_metadata=metadata, batch_size=batch_size)
