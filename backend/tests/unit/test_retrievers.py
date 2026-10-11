"""Unit tests for Dense, Sparse, RRF Fusion, Reranker, and HybridRetriever."""
import uuid

import pytest
from qdrant_client import QdrantClient

from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import DeterministicMockEmbedder
from packages.retrieval.fusion import ReciprocalRankFusion
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.models import RetrievalConfig, RetrievalResult
from packages.retrieval.qdrant_client import create_qdrant_client, ensure_collection
from packages.retrieval.reranker import LexicalSemanticMockReranker
from packages.retrieval.sparse import SparseRetriever


@pytest.fixture
def memory_client() -> QdrantClient:
    client = create_qdrant_client(in_memory=True)
    ensure_collection(
        client, collection_name="retrieval_test_chunks", dense_dim=384, recreate=True
    )
    return client


@pytest.fixture
def indexed_collection(
    memory_client: QdrantClient,
) -> tuple[QdrantClient, DeterministicMockEmbedder]:
    embedder = DeterministicMockEmbedder(dimension=384)
    indexer = QdrantIndexer(
        client=memory_client,
        dense_embedder=embedder,
        sparse_embedder=embedder,
        collection_name="retrieval_test_chunks",
    )

    chunks = [
        {
            "id": str(uuid.uuid4()),
            "text": "Apple iPhone net sales reached $201 billion in fiscal 2024.",
            "heading_path": "MD&A > iPhone",
            "page_start": 25,
            "page_end": 26,
            "chunk_type": "paragraph",
        },
        {
            "id": str(uuid.uuid4()),
            "text": "Apple Services revenue grew to $96 billion driven by advertising and cloud.",
            "heading_path": "MD&A > Services",
            "page_start": 27,
            "page_end": 28,
            "chunk_type": "paragraph",
        },
        {
            "id": str(uuid.uuid4()),
            "text": "Microsoft Azure cloud revenue increased 19% in fiscal 2024.",
            "heading_path": "Segment Results > Cloud",
            "page_start": 40,
            "page_end": 41,
            "chunk_type": "paragraph",
        },
        {
            "id": str(uuid.uuid4()),
            "text": "NVIDIA Data Center revenue surged to $47 billion driven by Hopper.",
            "heading_path": "Business Overview > Data Center",
            "page_start": 15,
            "page_end": 16,
            "chunk_type": "paragraph",
        },
    ]

    doc_meta_apple = {
        "document_id": "doc-apple",
        "company": "Apple Inc.",
        "year": 2024,
        "document_type": "10-K",
    }
    doc_meta_msft = {
        "document_id": "doc-msft",
        "company": "Microsoft Corporation",
        "year": 2024,
        "document_type": "10-K",
    }
    doc_meta_nvda = {
        "document_id": "doc-nvda",
        "company": "NVIDIA Corporation",
        "year": 2024,
        "document_type": "10-K",
    }

    indexer.index_chunks([chunks[0], chunks[1]], document_metadata=doc_meta_apple)
    indexer.index_chunks([chunks[2]], document_metadata=doc_meta_msft)
    indexer.index_chunks([chunks[3]], document_metadata=doc_meta_nvda)

    return memory_client, embedder


class TestRetrievers:
    def test_dense_retriever(self, indexed_collection):
        client, embedder = indexed_collection
        retriever = DenseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )

        results = retriever.retrieve(query="iPhone net sales", top_k=2)
        assert len(results) <= 2
        assert len(results) > 0
        assert results[0].chunk_id
        assert results[0].rank == 1

    def test_sparse_retriever(self, indexed_collection):
        client, embedder = indexed_collection
        retriever = SparseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )

        results = retriever.retrieve(query="Microsoft Azure cloud", top_k=2)
        assert len(results) > 0
        assert "Azure" in results[0].text or results[0].company == "Microsoft Corporation"

    def test_rrf_fusion_logic(self):
        c1 = RetrievalResult(chunk_id="c1", document_id="d1", score=0.9, text="Apple")
        c2 = RetrievalResult(chunk_id="c2", document_id="d1", score=0.8, text="Services")
        c3 = RetrievalResult(chunk_id="c3", document_id="d1", score=0.7, text="Cloud")

        dense_list = [c1, c2]
        sparse_list = [c2, c3]

        fusion = ReciprocalRankFusion(k=60)
        fused = fusion.fuse(dense_results=dense_list, sparse_results=sparse_list, fusion_k=3)

        assert len(fused) == 3
        # c2 appears in both lists, so its reciprocal rank sum is highest
        assert fused[0].chunk_id == "c2"
        assert fused[0].rank == 1

    def test_reranker_ordering(self):
        c1 = RetrievalResult(
            chunk_id="c1", document_id="d1", score=0.1, text="Unrelated text about cars"
        )
        c2 = RetrievalResult(
            chunk_id="c2",
            document_id="d1",
            score=0.2,
            text="Direct mention of iPhone sales revenue",
        )

        reranker = LexicalSemanticMockReranker()
        reranked = reranker.rerank(query="iPhone revenue", candidates=[c1, c2], top_k=2)

        assert len(reranked) == 2
        # c2 has high word overlap with query -> becomes rank 1
        assert reranked[0].chunk_id == "c2"
        assert reranked[0].rank == 1

    def test_hybrid_pipeline_and_diagnostics(self, indexed_collection):
        client, embedder = indexed_collection
        dense = DenseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )
        sparse = SparseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )
        reranker = LexicalSemanticMockReranker()

        config = RetrievalConfig(
            dense_k=30,
            sparse_k=30,
            fusion_k=20,
            rerank_k=10,
        )

        hybrid = HybridRetriever(
            dense_retriever=dense,
            sparse_retriever=sparse,
            reranker=reranker,
            config=config,
        )

        results, diag = hybrid.retrieve(query="Apple fiscal 2024 sales")
        assert len(results) > 0
        assert diag.total_latency_ms >= 0.0
        assert diag.dense_latency_ms >= 0.0
        assert diag.sparse_latency_ms >= 0.0
        assert diag.fusion_latency_ms >= 0.0
        assert diag.rerank_latency_ms >= 0.0
        assert diag.dense_candidates_count > 0
        assert diag.fused_candidates_count > 0

    def test_metadata_filters_applied_in_hybrid(self, indexed_collection):
        client, embedder = indexed_collection
        dense = DenseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )
        sparse = SparseRetriever(
            client=client, embedder=embedder, collection_name="retrieval_test_chunks"
        )
        hybrid = HybridRetriever(dense_retriever=dense, sparse_retriever=sparse)

        # Query about cloud, but filter strictly to Apple
        results, _ = hybrid.retrieve(
            query="revenue cloud growth",
            filters={"company": "Apple Inc."},
        )
        assert len(results) > 0
        assert all(r.company == "Apple Inc." for r in results)
