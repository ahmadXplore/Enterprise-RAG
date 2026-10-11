"""Unit tests for dense and sparse embedders."""
import pytest

from packages.retrieval.embeddings import (
    BM25SparseEmbedder,
    DeterministicMockEmbedder,
    FastEmbedDenseEmbedder,
)


class TestDeterministicMockEmbedder:
    def test_dense_dimension(self):
        embedder = DeterministicMockEmbedder(dimension=384)
        assert embedder.dimension == 384
        vecs = embedder.embed_texts(["Apple fiscal 2024 revenue"])
        assert len(vecs) == 1
        assert len(vecs[0]) == 384

    def test_dense_normalized(self):
        embedder = DeterministicMockEmbedder(dimension=384)
        vec = embedder.embed_query("Sample search text")
        norm = sum(x * x for x in vec)
        assert pytest.approx(norm, rel=1e-3) == 1.0

    def test_sparse_structure(self):
        embedder = DeterministicMockEmbedder()
        sparse = embedder.embed_sparse(["Apple Apple revenue"])
        assert len(sparse) == 1
        indices, values = sparse[0]
        assert len(indices) == len(values)
        assert len(indices) == 2  # "apple" and "revenue"
        # "apple" appeared twice, so its value should be 2.0
        assert 2.0 in values

    def test_empty_string_handling(self):
        embedder = DeterministicMockEmbedder()
        dense = embedder.embed_texts([""])
        assert dense[0] == [0.0] * 384
        sparse = embedder.embed_sparse([""])
        assert sparse[0] == ([], [])


class TestFastEmbedEmbedders:
    def test_fastembed_dense_embedding(self):
        embedder = FastEmbedDenseEmbedder()
        assert embedder.dimension == 384
        vec = embedder.embed_query("Apple total net sales")
        assert len(vec) == 384
        norm = sum(x * x for x in vec)
        assert pytest.approx(norm, rel=1e-2) == 1.0

    def test_fastembed_sparse_embedding(self):
        embedder = BM25SparseEmbedder()
        indices, values = embedder.embed_query_sparse("revenue net sales")
        assert len(indices) > 0
        assert len(indices) == len(values)
