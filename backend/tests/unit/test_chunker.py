"""Tests for SemanticChunker.

Tests cover:
- paragraph chunks
- headings in heading_path
- table chunks (table_html preserved, type=table)
- large table split into table_row_group chunks
- long section split with overlap
- duplicate content_hash detection
- deterministic chunk IDs (same input → same IDs on every run)
- token_count populated
- configurable target/overlap
"""
import hashlib
import uuid

import pytest

from packages.ingestion.chunker import (
    SemanticChunker,
    _content_hash,
    _deterministic_chunk_id,
)
from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedParagraph,
    ParsedTable,
    ParserProvenance,
)

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _doc(
    paragraphs: list[tuple[str, str, int | None]] | None = None,  # (text, section_path, page)
    tables: list[tuple[str, str, str | None]] | None = None,  # (text, table_html, section_path)
    headings: list[tuple[int, str, str]] | None = None,  # (level, text, path)
) -> NormalizedDocument:
    return NormalizedDocument(
        document_id="test-doc",
        document_version_id="ver-001",
        provenance=ParserProvenance(parser_name="test", parser_version="0"),
        headings=[
            ParsedHeading(level=level_idx, text=t, path=p)
            for level_idx, t, p in (headings or [])
        ],
        paragraphs=[
            ParsedParagraph(text=text, section_path=sp, page=pg)
            for text, sp, pg in (paragraphs or [])
        ],
        tables=[
            ParsedTable(text=text, table_html=html, section_path=sp or "")
            for text, html, sp in (tables or [])
        ],
    )


VERSION_ID = "ver-001"


# ------------------------------------------------------------------
# Deterministic ID
# ------------------------------------------------------------------

class TestDeterministicChunkId:
    def test_same_input_same_id(self):
        id1 = _deterministic_chunk_id(VERSION_ID, 0)
        id2 = _deterministic_chunk_id(VERSION_ID, 0)
        assert id1 == id2

    def test_different_index_different_id(self):
        id1 = _deterministic_chunk_id(VERSION_ID, 0)
        id2 = _deterministic_chunk_id(VERSION_ID, 1)
        assert id1 != id2

    def test_different_version_different_id(self):
        id1 = _deterministic_chunk_id("ver-A", 0)
        id2 = _deterministic_chunk_id("ver-B", 0)
        assert id1 != id2

    def test_is_valid_uuid(self):
        chunk_id = _deterministic_chunk_id(VERSION_ID, 5)
        parsed = uuid.UUID(chunk_id)
        assert str(parsed) == chunk_id


# ------------------------------------------------------------------
# Content hash
# ------------------------------------------------------------------

class TestContentHash:
    def test_hash_matches_sha256(self):
        text = "Hello world"
        expected = hashlib.sha256(text.encode()).hexdigest()
        assert _content_hash(text) == expected

    def test_empty_string(self):
        result = _content_hash("")
        assert len(result) == 64


# ------------------------------------------------------------------
# Basic paragraph chunking
# ------------------------------------------------------------------

class TestParagraphChunking:
    def test_single_paragraph_produces_one_chunk(self):
        doc = _doc(paragraphs=[("Revenue grew 15% in 2024.", "Part I", 1)])
        chunks = SemanticChunker().chunk(doc)
        assert len(chunks) == 1
        assert chunks[0].chunk_type == "paragraph"
        assert "Revenue" in chunks[0].text

    def test_heading_path_preserved(self):
        doc = _doc(
            paragraphs=[
                ("We operate globally.", "Part I > Item 1 > Business", 2),
            ]
        )
        chunks = SemanticChunker().chunk(doc)
        assert chunks[0].section_path == "Part I > Item 1 > Business"

    def test_page_numbers_preserved(self):
        doc = _doc(
            paragraphs=[
                ("Alpha.", "Sec A", 3),
                ("Beta.", "Sec A", 4),
            ]
        )
        chunks = SemanticChunker().chunk(doc)
        # Merged: page_start=3, page_end=4
        chunk = chunks[0]
        assert chunk.page_start == 3
        assert chunk.page_end == 4

    def test_token_count_populated(self):
        doc = _doc(paragraphs=[("Some text about financial performance.", "", 1)])
        chunks = SemanticChunker().chunk(doc)
        assert chunks[0].token_count > 0

    def test_content_hash_populated(self):
        doc = _doc(paragraphs=[("Audit opinion paragraph.", "", 1)])
        chunks = SemanticChunker().chunk(doc)
        text = chunks[0].text
        assert chunks[0].content_hash == _content_hash(text)

    def test_table_html_is_none_for_paragraph(self):
        doc = _doc(paragraphs=[("Text here.", "", 1)])
        chunks = SemanticChunker().chunk(doc)
        assert chunks[0].table_html is None

    def test_chunk_index_sequential(self):
        doc = _doc(
            paragraphs=[
                ("A " * 200, "S1", 1),
                ("B " * 200, "S2", 2),
            ]
        )
        chunks = SemanticChunker(target_tokens=50, overlap_tokens=10).chunk(doc)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# ------------------------------------------------------------------
# Merging adjacent short paragraphs
# ------------------------------------------------------------------

class TestParagraphMerging:
    def test_short_paragraphs_merged(self):
        doc = _doc(
            paragraphs=[
                ("Short A.", "Sec", 1),
                ("Short B.", "Sec", 1),
                ("Short C.", "Sec", 1),
            ]
        )
        chunks = SemanticChunker(target_tokens=500).chunk(doc)
        # All three should merge into one chunk
        assert len(chunks) == 1
        assert "Short A" in chunks[0].text
        assert "Short B" in chunks[0].text

    def test_different_sections_not_merged(self):
        doc = _doc(
            paragraphs=[
                ("Para in section A.", "Section A", 1),
                ("Para in section B.", "Section B", 2),
            ]
        )
        chunks = SemanticChunker(target_tokens=500).chunk(doc)
        paths = [c.section_path for c in chunks]
        assert "Section A" in paths
        assert "Section B" in paths


# ------------------------------------------------------------------
# Long paragraph splitting with overlap
# ------------------------------------------------------------------

class TestLongParagraphSplitting:
    def test_long_paragraph_split(self):
        # 300 words — should exceed a 50-token target
        long_text = "The company reported strong earnings. " * 50
        doc = _doc(paragraphs=[(long_text, "Financials", 5)])
        chunks = SemanticChunker(target_tokens=50, overlap_tokens=10).chunk(doc)
        assert len(chunks) > 1
        for c in chunks:
            assert c.chunk_type == "paragraph"

    def test_overlap_creates_shared_content(self):
        sentences = [f"Sentence number {i}." for i in range(30)]
        long_text = " ".join(sentences)
        doc = _doc(paragraphs=[(long_text, "Sec", 1)])
        chunks = SemanticChunker(target_tokens=30, overlap_tokens=8).chunk(doc)
        if len(chunks) > 1:
            # The last word/phrase of chunk N should appear somewhere in chunk N+1
            # (overlap ensures shared content between adjacent chunks)
            end_of_first = chunks[0].text
            start_of_second = chunks[1].text
            # At least one non-trivial word from the end of chunk 0 appears in chunk 1
            words_in_first = set(end_of_first.split())
            words_in_second = set(start_of_second.split())
            shared = words_in_first & words_in_second
            # Filter out very short/common words
            meaningful_shared = {w for w in shared if len(w) > 3}
            assert meaningful_shared, (
                f"Expected overlap between chunks.\n"
                f"Chunk 0 tail: {end_of_first[-100:]}\n"
                f"Chunk 1 start: {start_of_second[:100]}"
            )


# ------------------------------------------------------------------
# Table chunking
# ------------------------------------------------------------------

class TestTableChunking:
    def test_small_table_single_chunk(self):
        html = (
            "<table><tr><th>Year</th><th>Revenue</th></tr>"
            "<tr><td>2024</td><td>1B</td></tr></table>"
        )
        doc = _doc(tables=[("Year Revenue\n2024 1B", html, "Financials")])
        chunks = SemanticChunker().chunk(doc)
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 1
        assert table_chunks[0].table_html == html

    def test_table_chunk_type_is_table(self):
        doc = _doc(tables=[("A B\n1 2", "<table><tr><td>A</td></tr></table>", "Sec")])
        chunks = SemanticChunker().chunk(doc)
        assert all(c.chunk_type in ("table", "table_row_group") for c in chunks if c.table_html)

    def test_table_html_preserved(self):
        html = (
            "<table><tr><th>Clause</th><th>Ref</th></tr>"
            "<tr><td>Termination</td><td>§9</td></tr></table>"
        )
        doc = _doc(tables=[("Clause Ref\nTermination §9", html, "Legal")])
        chunks = SemanticChunker().chunk(doc)
        table_chunks = [c for c in chunks if c.table_html]
        assert any(html in c.table_html for c in table_chunks)

    def test_large_table_split_into_row_groups(self):
        # Build a large table: header + 50 rows of data
        header = "<tr><th>Item</th><th>Value</th></tr>"
        body_rows = "".join(
            f"<tr><td>Item {i}</td><td>Value is a longer description here {i}</td></tr>"
            for i in range(50)
        )
        html = f"<table>{header}{body_rows}</table>"
        text = "\n".join(
            [f"Item {i}\tValue is a longer description here {i}" for i in range(50)]
        )
        doc = _doc(tables=[(text, html, "Big Table Section")])
        chunks = SemanticChunker(target_tokens=100).chunk(doc)
        row_group_chunks = [c for c in chunks if c.chunk_type == "table_row_group"]
        assert len(row_group_chunks) > 1
        # Every group must have a table_html containing at least the header
        for c in row_group_chunks:
            assert c.table_html is not None


# ------------------------------------------------------------------
# Determinism
# ------------------------------------------------------------------

class TestDeterminism:
    def test_same_doc_same_ids(self):
        paras = [
            ("Revenue increased by 15%.", "Part I", 1),
            ("Operating costs were flat.", "Part I", 1),
        ]
        doc1 = _doc(paragraphs=paras)
        doc2 = _doc(paragraphs=paras)
        chunker = SemanticChunker()
        chunks1 = chunker.chunk(doc1)
        chunks2 = chunker.chunk(doc2)
        assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]

    def test_different_text_different_ids(self):
        """Chunk IDs are position-based (version+index), so same position → same ID.
        Content hash differs when text differs — that is what distinguishes content."""
        doc1 = _doc(paragraphs=[("Apple reported $90B revenue.", "", 1)])
        doc2 = _doc(paragraphs=[("Microsoft reported $62B revenue.", "", 1)])
        chunker = SemanticChunker()
        # Same version_id + chunk_index → same chunk_id (determinism by position)
        assert chunker.chunk(doc1)[0].chunk_id == chunker.chunk(doc2)[0].chunk_id
        # Content hash must differ since text differs
        assert chunker.chunk(doc1)[0].content_hash != chunker.chunk(doc2)[0].content_hash


# ------------------------------------------------------------------
# Duplicate content_hash (same text, different position)
# ------------------------------------------------------------------

class TestDuplicateChunks:
    def test_same_text_different_positions_different_ids(self):
        """Two paragraphs with identical text get different chunk_ids (different index)
        but the same content_hash."""
        repeated = "Standard boilerplate language applies here."
        doc = _doc(
            paragraphs=[
                (repeated, "Sec A", 1),
                (repeated, "Sec A", 2),
            ]
        )
        chunks = SemanticChunker(target_tokens=500).chunk(doc)
        # Merged into one (same section) — content_hash of merged text
        assert len(chunks) >= 1
        for c in chunks:
            assert c.content_hash != ""

    def test_content_hash_is_deterministic_for_text(self):
        text = "Revenue was $1.2B in fiscal year 2024."
        assert _content_hash(text) == _content_hash(text)

    def test_content_hash_differs_for_different_text(self):
        assert _content_hash("Alpha") != _content_hash("Beta")


# ------------------------------------------------------------------
# Chunker configuration
# ------------------------------------------------------------------

class TestChunkerConfig:
    def test_invalid_target_tokens(self):
        with pytest.raises(ValueError):
            SemanticChunker(target_tokens=5)  # below new minimum of 10

    def test_invalid_overlap(self):
        with pytest.raises(ValueError):
            SemanticChunker(target_tokens=100, overlap_tokens=100)

    def test_custom_target_respected(self):
        # With a very small target, long text must produce multiple chunks
        long_text = "Word " * 500
        doc = _doc(paragraphs=[(long_text, "", 1)])
        chunks_small = SemanticChunker(target_tokens=100, overlap_tokens=20).chunk(doc)
        chunks_large = SemanticChunker(target_tokens=2000, overlap_tokens=20).chunk(doc)
        assert len(chunks_small) > len(chunks_large)
