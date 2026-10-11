"""Dense and Sparse embedding services for RAG retrieval."""
import hashlib
import math
import time
from typing import Protocol

try:
    from fastembed import SparseTextEmbedding, TextEmbedding
    _FASTEMBED_AVAILABLE = True
except ImportError:
    _FASTEMBED_AVAILABLE = False


class DenseEmbedder(Protocol):
    """Protocol for dense vector embedders."""

    @property
    def dimension(self) -> int: ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, query: str) -> list[float]: ...


class SparseEmbedder(Protocol):
    """Protocol for sparse BM25 vector embedders."""

    def embed_sparse(self, texts: list[str]) -> list[tuple[list[int], list[float]]]: ...

    def embed_query_sparse(self, query: str) -> tuple[list[int], list[float]]: ...


class FastEmbedDenseEmbedder:
    """Dense embedding service using FastEmbed all-MiniLM-L6-v2 (384 dims)."""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        if not _FASTEMBED_AVAILABLE:
            raise RuntimeError("fastembed is required for FastEmbedDenseEmbedder")
        self.model_name = model_name
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                self._model = TextEmbedding(model_name=model_name)
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            if last_exc:
                raise last_exc
        self._dim = 384

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = list(self._model.embed(texts))
        return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings]

    def embed_query(self, query: str) -> list[float]:
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self._dim


class BM25SparseEmbedder:
    """Sparse BM25 embedding service using FastEmbed Qdrant/bm25."""

    def __init__(self, model_name: str = "Qdrant/bm25") -> None:
        if not _FASTEMBED_AVAILABLE:
            raise RuntimeError("fastembed is required for BM25SparseEmbedder")
        self.model_name = model_name
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                self._model = SparseTextEmbedding(model_name=model_name)
                break
            except Exception as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            if last_exc:
                raise last_exc

    def embed_sparse(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        if not texts:
            return []
        embeddings = list(self._model.embed(texts))
        output: list[tuple[list[int], list[float]]] = []
        for emb in embeddings:
            indices = emb.indices.tolist() if hasattr(emb.indices, "tolist") else list(emb.indices)
            values = emb.values.tolist() if hasattr(emb.values, "tolist") else list(emb.values)
            output.append((indices, values))
        return output

    def embed_query_sparse(self, query: str) -> tuple[list[int], list[float]]:
        results = self.embed_sparse([query])
        return results[0] if results else ([], [])


class DeterministicMockEmbedder:
    """Deterministic, lightweight embedder for fast unit tests without network or ONNX.

    Dense: produces 384-dimensional unit-length vectors derived from MD5/SHA256 text hash.
    Sparse: produces token hash indices and frequencies derived from whitespace-split words.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self._dim
            if not text:
                results.append(vec)
                continue
            words = text.lower().split()
            for word in words:
                h = int(hashlib.md5(word.encode("utf-8"), usedforsecurity=False).hexdigest(), 16)
                idx = h % self._dim
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec))
            if norm > 0:
                vec = [x / norm for x in vec]
            results.append(vec)
        return results

    def embed_query(self, query: str) -> list[float]:
        results = self.embed_texts([query])
        return results[0] if results else [0.0] * self._dim

    def embed_sparse(self, texts: list[str]) -> list[tuple[list[int], list[float]]]:
        results: list[tuple[list[int], list[float]]] = []
        for text in texts:
            if not text:
                results.append(([], []))
                continue
            words = text.lower().split()
            counts: dict[int, float] = {}
            for word in words:
                # 31-bit non-negative integer for Qdrant sparse index
                h_hex = hashlib.md5(
                    word.encode("utf-8"), usedforsecurity=False
                ).hexdigest()[:7]
                idx = int(h_hex, 16)
                counts[idx] = counts.get(idx, 0.0) + 1.0
            sorted_items = sorted(counts.items())
            indices = [k for k, _ in sorted_items]
            values = [v for _, v in sorted_items]
            results.append((indices, values))
        return results

    def embed_query_sparse(self, query: str) -> tuple[list[int], list[float]]:
        results = self.embed_sparse([query])
        return results[0] if results else ([], [])
