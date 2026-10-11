"""End-to-end integration test of ingestion chunks to Qdrant indexing and hybrid retrieval."""
import uuid

import pytest

from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.models import RetrievalConfig
from packages.retrieval.qdrant_client import create_qdrant_client, ensure_collection
from packages.retrieval.reranker import FastEmbedReranker
from packages.retrieval.sparse import SparseRetriever


@pytest.fixture(scope="module")
def real_models():
    """Load FastEmbed models once for integration testing."""
    dense_embedder = FastEmbedDenseEmbedder()
    sparse_embedder = BM25SparseEmbedder()
    reranker = FastEmbedReranker()
    return dense_embedder, sparse_embedder, reranker


def test_end_to_end_hybrid_retrieval(real_models):
    dense_embedder, sparse_embedder, reranker = real_models

    client = create_qdrant_client(in_memory=True)
    collection_name = "e2e_hybrid_chunks"
    ensure_collection(client, collection_name=collection_name, dense_dim=384, recreate=True)

    indexer = QdrantIndexer(
        client=client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        collection_name=collection_name,
    )

    chunk_apple_id = str(uuid.uuid4())
    chunk_msft_id = str(uuid.uuid4())
    chunk_nvda_id = str(uuid.uuid4())

    chunks = [
        {
            "id": chunk_apple_id,
            "text": (
                "Total net sales of iPhone were $201,183 million in fiscal 2024, "
                "representing the largest revenue source for Apple."
            ),
            "heading_path": "Part II > Item 7 > Products Net Sales",
            "page_start": 25,
            "page_end": 26,
            "chunk_type": "paragraph",
        },
        {
            "id": chunk_msft_id,
            "text": (
                "Intelligent Cloud revenue was $105,362 million in fiscal 2024, "
                "driven by Azure and other cloud services growth."
            ),
            "heading_path": "Part II > Item 7 > Intelligent Cloud",
            "page_start": 38,
            "page_end": 39,
            "chunk_type": "paragraph",
        },
        {
            "id": chunk_nvda_id,
            "text": (
                "Data Center segment revenue grew 217% to $47,525 million for fiscal 2024, "
                "driven by the NVIDIA HGX platform."
            ),
            "heading_path": "Part I > Item 1 > Data Center Overview",
            "page_start": 12,
            "page_end": 13,
            "chunk_type": "paragraph",
        },
    ]

    indexer.index_chunks(
        [chunks[0]],
        document_metadata={
            "document_id": "doc-aapl-2024",
            "company": "Apple Inc.",
            "year": 2024,
            "document_type": "10-K",
        },
    )
    indexer.index_chunks(
        [chunks[1]],
        document_metadata={
            "document_id": "doc-msft-2024",
            "company": "Microsoft Corporation",
            "year": 2024,
            "document_type": "10-K",
        },
    )
    indexer.index_chunks(
        [chunks[2]],
        document_metadata={
            "document_id": "doc-nvda-2024",
            "company": "NVIDIA Corporation",
            "year": 2024,
            "document_type": "10-K",
        },
    )

    assert client.count(collection_name=collection_name).count == 3

    dense = DenseRetriever(client=client, embedder=dense_embedder, collection_name=collection_name)
    sparse = SparseRetriever(
        client=client, embedder=sparse_embedder, collection_name=collection_name
    )
    hybrid = HybridRetriever(
        dense_retriever=dense,
        sparse_retriever=sparse,
        reranker=reranker,
        config=RetrievalConfig(dense_k=10, sparse_k=10, fusion_k=5, rerank_k=3),
    )

    # Search for iPhone revenue
    results, diag = hybrid.retrieve(query="What were the total iPhone net sales in 2024?")
    assert len(results) > 0
    top_result = results[0]

    # Verify vector maps back to PostgreSQL chunk ID
    assert top_result.chunk_id == chunk_apple_id
    assert top_result.company == "Apple Inc."
    assert top_result.year == 2024
    assert "iPhone were $201,183 million" in top_result.text
    assert diag.total_latency_ms > 0
    assert diag.reranked_candidates_count > 0
