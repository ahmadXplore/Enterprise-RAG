"""Data models for retrieval results, diagnostics, and configurations."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RetrievalResult:
    """A single retrieved chunk with metadata and relevance score."""

    chunk_id: str
    document_id: str
    score: float
    text: str
    company: str = ""
    year: int = 0
    document_type: str = ""
    section: str = ""
    page_start: int | None = None
    page_end: int | None = None
    chunk_type: str | None = None
    rank: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalDiagnostics:
    """Latency and candidate count diagnostics across retrieval pipeline stages."""

    dense_latency_ms: float = 0.0
    sparse_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    dense_candidates_count: int = 0
    sparse_candidates_count: int = 0
    fused_candidates_count: int = 0
    reranked_candidates_count: int = 0


@dataclass
class RetrievalConfig:
    """Configurable pipeline candidate thresholds and parameters."""

    dense_k: int = 30
    sparse_k: int = 30
    fusion_k: int = 20
    rerank_k: int = 10
    rrf_k: int = 60
