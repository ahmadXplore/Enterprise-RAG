"""Tests for ChunkStore.

Tests cover:
- Inserts sections and chunks into the database
- Upsert on re-parse does not duplicate chunks
- Updates DocumentVersion.parse_status and Document.status to 'chunked'
- Raises on missing DocumentVersion
- All queries use the async session fixture (in-memory SQLite)
"""
import uuid
from datetime import UTC, datetime

import pytest
from apps.api.app.models.document import Document, DocumentChunk, DocumentSection, DocumentVersion
from sqlalchemy import select

from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.chunker import ChunkRecord, _content_hash, _deterministic_chunk_id

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _create_document_and_version(session, document_id, version_id):
    """Insert a Document + DocumentVersion row for tests."""
    doc = Document(
        id=document_id,
        title="Test Doc",
        source_type="sec",
        document_type="annual_report",
        content_hash="a" * 64,
        status="registered",
    )
    session.add(doc)
    await session.flush()

    version = DocumentVersion(
        id=version_id,
        document_id=document_id,
        version_label="v1.0",
        source_file_path="/data/raw/test.pdf",
        parse_status="pending",
    )
    session.add(version)
    await session.flush()
    return doc, version


def _make_chunk(version_id: str, index: int, text: str = "Sample text.") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=_deterministic_chunk_id(version_id, index),
        document_version_id=version_id,
        section_path="Part I > Revenue",
        chunk_index=index,
        chunk_type="paragraph",
        text=text,
        table_html=None,
        page_start=1,
        page_end=1,
        token_count=len(text.split()),
        content_hash=_content_hash(text),
    )


def _make_table_chunk(version_id: str, index: int) -> ChunkRecord:
    html = "<table><tr><td>Year</td><td>Revenue</td></tr></table>"
    text = "Year Revenue"
    return ChunkRecord(
        chunk_id=_deterministic_chunk_id(version_id, index),
        document_version_id=version_id,
        section_path="Financials",
        chunk_index=index,
        chunk_type="table",
        text=text,
        table_html=html,
        page_start=5,
        page_end=5,
        token_count=2,
        content_hash=_content_hash(text),
    )


def _make_section(doc_version_id: uuid.UUID, heading: str, order: int = 0) -> dict:
    return {
        "id": uuid.uuid4(),
        "document_version_id": doc_version_id,
        "parent_section_id": None,
        "heading": heading,
        "heading_level": 1,
        "section_order": order,
        "page_start": 1,
        "page_end": 1,
        "path": heading,
        "created_at": datetime.now(UTC),
    }


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestChunkStoreInsert:
    async def test_inserts_chunks(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunks = [_make_chunk(str(ver_id), i) for i in range(3)]
        store = ChunkStore(db_session)
        await store.store(ver_id, [], chunks)

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 3

    async def test_inserts_sections(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        sections = [_make_section(ver_id, f"Heading {i}", i) for i in range(2)]
        store = ChunkStore(db_session)
        await store.store(ver_id, sections, [])

        result = await db_session.execute(
            select(DocumentSection).where(DocumentSection.document_version_id == ver_id)
        )
        rows = result.scalars().all()
        assert len(rows) == 2

    async def test_table_chunk_html_stored(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunks = [_make_table_chunk(str(ver_id), 0)]
        store = ChunkStore(db_session)
        await store.store(ver_id, [], chunks)

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        row = result.scalar_one()
        assert row.table_html is not None
        assert "<table" in row.table_html
        assert row.chunk_type == "table"

    async def test_marks_version_chunked(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        _, version = await _create_document_and_version(db_session, doc_id, ver_id)

        store = ChunkStore(db_session)
        await store.store(ver_id, [], [_make_chunk(str(ver_id), 0)])

        await db_session.refresh(version)
        assert version.parse_status == "chunked"

    async def test_marks_document_chunked(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        doc, _ = await _create_document_and_version(db_session, doc_id, ver_id)

        store = ChunkStore(db_session)
        await store.store(ver_id, [], [_make_chunk(str(ver_id), 0)])

        await db_session.refresh(doc)
        assert doc.status == "chunked"

    async def test_raises_on_missing_version(self, db_session):
        fake_id = uuid.uuid4()
        store = ChunkStore(db_session)
        with pytest.raises(ValueError, match="not found"):
            await store.store(fake_id, [], [])


class TestChunkStoreUpsert:
    async def test_upsert_does_not_duplicate(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunk = _make_chunk(str(ver_id), 0, "Original text.")
        store = ChunkStore(db_session)
        await store.store(ver_id, [], [chunk])

        # Second store with updated text — same chunk_index
        chunk_updated = _make_chunk(str(ver_id), 0, "Updated text after re-parse.")
        await store.store(ver_id, [], [chunk_updated])

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        rows = result.scalars().all()
        # Must not duplicate — still exactly one row for this chunk_index
        assert len(rows) == 1
        assert rows[0].text == "Updated text after re-parse."

    async def test_upsert_updates_content_hash(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunk_v1 = _make_chunk(str(ver_id), 0, "Version one text.")
        store = ChunkStore(db_session)
        await store.store(ver_id, [], [chunk_v1])

        chunk_v2 = _make_chunk(str(ver_id), 0, "Version two text — different content.")
        await store.store(ver_id, [], [chunk_v2])

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        row = result.scalar_one()
        assert row.content_hash == _content_hash("Version two text — different content.")


class TestChunkStoreFieldMapping:
    async def test_heading_path_stored_in_heading_path_column(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunk = _make_chunk(str(ver_id), 0)
        chunk.section_path = "Part II > Item 8 > Financial Statements"
        store = ChunkStore(db_session)
        await store.store(ver_id, [], [chunk])

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        row = result.scalar_one()
        assert row.heading_path == "Part II > Item 8 > Financial Statements"

    async def test_page_numbers_stored(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunk = _make_chunk(str(ver_id), 0)
        chunk.page_start = 10
        chunk.page_end = 12
        store = ChunkStore(db_session)
        await store.store(ver_id, [], [chunk])

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        row = result.scalar_one()
        assert row.page_start == 10
        assert row.page_end == 12

    async def test_token_count_stored(self, db_session):
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        await _create_document_and_version(db_session, doc_id, ver_id)

        chunk = _make_chunk(str(ver_id), 0)
        chunk.token_count = 42
        store = ChunkStore(db_session)
        await store.store(ver_id, [], [chunk])

        result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_version_id == ver_id)
        )
        row = result.scalar_one()
        assert row.token_count == 42
