"""Modular retrieval package: Embeddings, Qdrant Indexing, Hybrid Search, RRF, and Reranking."""
from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import (
    BM25SparseEmbedder,
    DenseEmbedder,
    DeterministicMockEmbedder,
    FastEmbedDenseEmbedder,
    SparseEmbedder,
)
from packages.retrieval.fusion import ReciprocalRankFusion
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.indexer import QdrantIndexer, build_metadata_filter
from packages.retrieval.injection_filter import FilterResult, PromptInjectionFilter
from packages.retrieval.models import (
    RetrievalConfig,
    RetrievalDiagnostics,
    RetrievalResult,
)
from packages.retrieval.qdrant_client import (
    DEFAULT_COLLECTION,
    create_qdrant_client,
    ensure_collection,
)
from packages.retrieval.reranker import (
    FastEmbedReranker,
    LexicalSemanticMockReranker,
    Reranker,
)
from packages.retrieval.sparse import SparseRetriever

__all__ = [
    "BM25SparseEmbedder",
    "DEFAULT_COLLECTION",
    "DenseEmbedder",
    "DenseRetriever",
    "DeterministicMockEmbedder",
    "FastEmbedDenseEmbedder",
    "FastEmbedReranker",
    "FilterResult",
    "HybridRetriever",
    "LexicalSemanticMockReranker",
    "PromptInjectionFilter",
    "QdrantIndexer",
    "ReciprocalRankFusion",
    "Reranker",
    "RetrievalConfig",
    "RetrievalDiagnostics",
    "RetrievalResult",
    "SparseEmbedder",
    "SparseRetriever",
    "build_metadata_filter",
    "create_qdrant_client",
    "ensure_collection",
]
