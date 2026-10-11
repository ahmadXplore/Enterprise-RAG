"""Unit tests for Qdrant indexing, idempotency, metadata payloads, and filtering."""
import uuid

import pytest
from qdrant_client import QdrantClient

from packages.retrieval.embeddings import DeterministicMockEmbedder
from packages.retrieval.indexer import QdrantIndexer, build_metadata_filter
from packages.retrieval.qdrant_client import create_qdrant_client, ensure_collection


class MockChunk:
    def __init__(
        self,
        chunk_id: uuid.UUID | str,
        text: str,
        heading_path: str = "Item 7 > MD&A",
        page_start: int = 25,
        page_end: int = 26,
        chunk_type: str = "paragraph",
    ) -> None:
        self.id = uuid.UUID(str(chunk_id)) if not isinstance(chunk_id, uuid.UUID) else chunk_id
        self.text = text
        self.heading_path = heading_path
        self.page_start = page_start
        self.page_end = page_end
        self.chunk_type = chunk_type
        self.token_count = len(text.split())
        self.content_hash = "fake-hash"


@pytest.fixture
def memory_client() -> QdrantClient:
    client = create_qdrant_client(in_memory=True)
    ensure_collection(client, collection_name="test_chunks", dense_dim=384, recreate=True)
    return client


@pytest.fixture
def indexer(memory_client: QdrantClient) -> QdrantIndexer:
    embedder = DeterministicMockEmbedder(dimension=384)
    return QdrantIndexer(
        client=memory_client,
        dense_embedder=embedder,
        sparse_embedder=embedder,
        collection_name="test_chunks",
    )


class TestQdrantIndexer:
    def test_indexing_point_id_matches_postgres_chunk_id(
        self, indexer: QdrantIndexer, memory_client: QdrantClient
    ):
        chunk_id = uuid.uuid4()
        chunk = MockChunk(chunk_id=chunk_id, text="Revenue was $100B in 2024.")
        doc_meta = {
            "document_id": str(uuid.uuid4()),
            "company": "Apple Inc.",
            "year": 2024,
            "document_type": "10-K",
        }

        indexed = indexer.index_chunks([chunk], document_metadata=doc_meta)
        assert indexed == 1

        # Verify point exists in Qdrant with identical point ID
        point = memory_client.retrieve(collection_name="test_chunks", ids=[str(chunk_id)])
        assert len(point) == 1
        assert point[0].id == str(chunk_id)
        assert point[0].payload["chunk_id"] == str(chunk_id)

    def test_payload_schema_completeness(
        self, indexer: QdrantIndexer, memory_client: QdrantClient
    ):
        chunk_id = uuid.uuid4()
        doc_id = str(uuid.uuid4())
        chunk = MockChunk(
            chunk_id=chunk_id,
            text="Products gross margin reached 37.1%.",
            heading_path="Item 7 > Gross Margin",
            page_start=30,
            page_end=31,
            chunk_type="table",
        )
        doc_meta = {
            "document_id": doc_id,
            "company": "Apple Inc.",
            "year": 2024,
            "document_type": "10-K",
        }

        indexer.index_chunks([chunk], document_metadata=doc_meta)
        point = memory_client.retrieve(collection_name="test_chunks", ids=[str(chunk_id)])[0]
        payload = point.payload

        # Required fields check
        assert payload["chunk_id"] == str(chunk_id)
        assert payload["document_id"] == doc_id
        assert payload["company"] == "Apple Inc."
        assert payload["year"] == 2024
        assert payload["document_type"] == "10-K"
        assert payload["section"] == "Item 7 > Gross Margin"
        assert payload["page_start"] == 30
        assert payload["page_end"] == 31
        assert payload["chunk_type"] == "table"

    def test_duplicate_indexing_is_idempotent(
        self, indexer: QdrantIndexer, memory_client: QdrantClient
    ):
        chunk_id = uuid.uuid4()
        chunk = MockChunk(chunk_id=chunk_id, text="Initial text")
        doc_meta = {
            "document_id": str(uuid.uuid4()),
            "company": "Apple Inc.",
            "year": 2024,
            "document_type": "10-K",
        }

        # First indexing
        indexer.index_chunks([chunk], document_metadata=doc_meta)
        count_first = memory_client.count(collection_name="test_chunks").count
        assert count_first == 1

        # Second indexing with same chunk ID (updated text)
        updated_chunk = MockChunk(chunk_id=chunk_id, text="Updated text after reparse")
        indexer.index_chunks([updated_chunk], document_metadata=doc_meta)
        count_second = memory_client.count(collection_name="test_chunks").count

        # Must not create duplicate logical points
        assert count_second == 1

        # Verify updated payload
        point = memory_client.retrieve(collection_name="test_chunks", ids=[str(chunk_id)])[0]
        assert point.payload["text"] == "Updated text after reparse"

    def test_reindex_document(self, indexer: QdrantIndexer, memory_client: QdrantClient):
        doc_id = str(uuid.uuid4())
        doc_meta = {
            "document_id": doc_id,
            "company": "Microsoft Corporation",
            "year": 2024,
            "document_type": "10-K",
        }

        # Index 3 initial chunks
        c1, c2, c3 = (
            MockChunk(uuid.uuid4(), "Chunk 1"),
            MockChunk(uuid.uuid4(), "Chunk 2"),
            MockChunk(uuid.uuid4(), "Chunk 3"),
        )
        indexer.index_chunks([c1, c2, c3], document_metadata=doc_meta)
        assert memory_client.count(collection_name="test_chunks").count == 3

        # Re-index with 2 new chunks for the same document
        new_c1 = MockChunk(uuid.uuid4(), "New Chunk A")
        new_c2 = MockChunk(uuid.uuid4(), "New Chunk B")
        indexer.reindex_document(
            document_id=doc_id, chunks=[new_c1, new_c2], document_metadata=doc_meta
        )

        # Old chunks removed, only new chunks remain
        assert memory_client.count(collection_name="test_chunks").count == 2
        old_points = memory_client.retrieve(collection_name="test_chunks", ids=[str(c1.id)])
        assert len(old_points) == 0

    def test_metadata_filtering(self, indexer: QdrantIndexer, memory_client: QdrantClient):
        # Index chunks from two different companies and years
        doc_aapl = {
            "document_id": "doc-aapl",
            "company": "Apple Inc.",
            "year": 2024,
            "document_type": "10-K",
        }
        doc_msft = {
            "document_id": "doc-msft",
            "company": "Microsoft Corporation",
            "year": 2023,
            "document_type": "10-K",
        }

        c_aapl = MockChunk(uuid.uuid4(), "Apple iPhone sales")
        c_msft = MockChunk(uuid.uuid4(), "Microsoft Azure cloud")

        indexer.index_chunks([c_aapl], document_metadata=doc_aapl)
        indexer.index_chunks([c_msft], document_metadata=doc_msft)

        # Filter by company
        f_aapl = build_metadata_filter({"company": "Apple Inc."})
        res_aapl = memory_client.query_points(
            collection_name="test_chunks",
            query=[0.0] * 384,
            using="dense",
            query_filter=f_aapl,
            limit=10,
        )
        assert len(res_aapl.points) == 1
        assert res_aapl.points[0].payload["company"] == "Apple Inc."

        # Filter by year
        f_2023 = build_metadata_filter({"year": 2023})
        res_2023 = memory_client.query_points(
            collection_name="test_chunks",
            query=[0.0] * 384,
            using="dense",
            query_filter=f_2023,
            limit=10,
        )
        assert len(res_2023.points) == 1
        assert res_2023.points[0].payload["company"] == "Microsoft Corporation"

        # Pre-retrieval authorization filter (Rule 12)
        f_auth = build_metadata_filter({"authorized_document_ids": ["doc-aapl"]})
        res_auth = memory_client.query_points(
            collection_name="test_chunks",
            query=[0.0] * 384,
            using="dense",
            query_filter=f_auth,
            limit=10,
        )
        assert len(res_auth.points) == 1
        assert res_auth.points[0].payload["document_id"] == "doc-aapl"
