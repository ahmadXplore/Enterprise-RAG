"""Qdrant connection factory and collection configuration for hybrid retrieval."""
from qdrant_client import QdrantClient, models

DEFAULT_COLLECTION = "enterprise_rag_chunks"


def create_qdrant_client(
    url: str | None = None,
    api_key: str | None = None,
    in_memory: bool = False,
    path: str | None = None,
) -> QdrantClient:
    """Create a configured QdrantClient instance.

    Args:
        url: Remote Qdrant server URL (e.g. http://localhost:6333).
        api_key: Optional Qdrant API key.
        in_memory: If True, uses embedded in-memory instance for testing.
        path: Optional local filesystem path for disk-backed local storage.
    """
    if in_memory:
        return QdrantClient(":memory:")
    if path:
        return QdrantClient(path=path)
    if url:
        return QdrantClient(url=url, api_key=api_key)
    # Default to memory if nothing is configured
    return QdrantClient(":memory:")


def ensure_collection(
    client: QdrantClient,
    collection_name: str = DEFAULT_COLLECTION,
    dense_dim: int = 384,
    recreate: bool = False,
) -> None:
    """Ensure a Qdrant collection exists with dual dense/sparse vector configuration.

    Vectors:
        dense: Cosine distance, specified dense dimension (384 for all-MiniLM-L6-v2).
        sparse: Modifier.IDF for BM25 term weighting.

    Payload indexes are created for metadata filtering fields.
    """
    collection_exists = False
    try:
        collections = client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)
    except Exception:  # noqa: BLE001
        collection_exists = False

    if collection_exists and recreate:
        client.delete_collection(collection_name=collection_name)
        collection_exists = False

    if not collection_exists:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF),
            },
        )

        # Create payload indexes for metadata filtering
        for field, schema in [
            ("company", models.PayloadSchemaType.KEYWORD),
            ("year", models.PayloadSchemaType.INTEGER),
            ("document_type", models.PayloadSchemaType.KEYWORD),
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("chunk_type", models.PayloadSchemaType.KEYWORD),
        ]:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception:  # noqa: BLE001, S110
                pass
