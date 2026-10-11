"""Tests for DocumentNormalizer.

Tests cover:
- Produces correct DocumentSection dicts from heading hierarchy
- Produces correct ChunkRecord list
- Section IDs linked correctly (parent_section_id)
- Empty doc produces empty lists
"""
import uuid

from packages.ingestion.normalizer import DocumentNormalizer, _build_sections
from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedParagraph,
    ParserProvenance,
)


def _doc_with_headings(*headings: tuple[int, str]) -> NormalizedDocument:
    return NormalizedDocument(
        document_id="doc-norm",
        document_version_id="ver-norm",
        provenance=ParserProvenance(parser_name="t", parser_version="0"),
        headings=[ParsedHeading(level=level_idx, text=t, path=t) for level_idx, t in headings],
        paragraphs=[
            ParsedParagraph(text=f"Para under {t}.", section_path=t, page=i + 1)
            for i, (_, t) in enumerate(headings)
        ],
    )


VERSION_UUID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class TestBuildSections:
    def test_empty_headings(self):
        doc = NormalizedDocument(
            document_id="x",
            document_version_id="y",
            provenance=ParserProvenance(parser_name="t", parser_version="0"),
        )
        sections = _build_sections(doc, VERSION_UUID)
        assert sections == []

    def test_single_heading(self):
        doc = _doc_with_headings((1, "Introduction"))
        sections = _build_sections(doc, VERSION_UUID)
        assert len(sections) == 1
        s = sections[0]
        assert s["heading"] == "Introduction"
        assert s["heading_level"] == 1
        assert s["parent_section_id"] is None
        assert s["document_version_id"] == VERSION_UUID

    def test_nested_headings_parent_linked(self):
        doc = _doc_with_headings(
            (1, "Part I"),
            (2, "Item 1"),
            (3, "Business"),
        )
        sections = _build_sections(doc, VERSION_UUID)
        assert len(sections) == 3
        part1 = sections[0]
        item1 = sections[1]
        business = sections[2]

        assert part1["parent_section_id"] is None
        assert item1["parent_section_id"] == part1["id"]
        assert business["parent_section_id"] == item1["id"]

    def test_sibling_headings_share_parent(self):
        doc = _doc_with_headings(
            (1, "Part I"),
            (2, "Section A"),
            (2, "Section B"),
        )
        sections = _build_sections(doc, VERSION_UUID)
        # Both h2s should have Part I as parent
        assert sections[1]["parent_section_id"] == sections[0]["id"]
        assert sections[2]["parent_section_id"] == sections[0]["id"]

    def test_section_order_sequential(self):
        doc = _doc_with_headings((1, "A"), (1, "B"), (1, "C"))
        sections = _build_sections(doc, VERSION_UUID)
        orders = [s["section_order"] for s in sections]
        assert orders == [0, 1, 2]

    def test_section_path_preserved(self):
        doc = _doc_with_headings((1, "Revenue"))
        doc.headings[0].path = "Part II > Revenue"
        sections = _build_sections(doc, VERSION_UUID)
        assert sections[0]["path"] == "Part II > Revenue"

    def test_all_sections_have_unique_ids(self):
        doc = _doc_with_headings((1, "A"), (2, "B"), (3, "C"))
        sections = _build_sections(doc, VERSION_UUID)
        ids = [s["id"] for s in sections]
        assert len(ids) == len(set(ids))


class TestDocumentNormalizer:
    def test_empty_document(self):
        doc = NormalizedDocument(
            document_id="x",
            document_version_id="y",
            provenance=ParserProvenance(parser_name="t", parser_version="0"),
        )
        normalizer = DocumentNormalizer()
        sections, chunks = normalizer.normalize(doc, VERSION_UUID)
        assert sections == []
        assert chunks == []

    def test_returns_sections_and_chunks(self):
        doc = _doc_with_headings((1, "Introduction"), (2, "Background"))
        normalizer = DocumentNormalizer()
        sections, chunks = normalizer.normalize(doc, VERSION_UUID)
        assert len(sections) == 2
        assert len(chunks) > 0

    def test_chunks_have_version_id(self):
        doc = _doc_with_headings((1, "Intro"))
        normalizer = DocumentNormalizer()
        _, chunks = normalizer.normalize(doc, VERSION_UUID)
        for c in chunks:
            assert c.document_version_id == "ver-norm"

    def test_section_ids_are_uuids(self):
        doc = _doc_with_headings((1, "Part I"), (2, "Item 1"))
        normalizer = DocumentNormalizer()
        sections, _ = normalizer.normalize(doc, VERSION_UUID)
        for s in sections:
            assert isinstance(s["id"], uuid.UUID)

    def test_chunks_are_deterministic_across_calls(self):
        doc = _doc_with_headings((1, "Revenue"), (2, "Expenses"))
        normalizer = DocumentNormalizer()
        _, chunks1 = normalizer.normalize(doc, VERSION_UUID)
        _, chunks2 = normalizer.normalize(doc, VERSION_UUID)
        assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]

    def test_configurable_token_params(self):
        doc = _doc_with_headings((1, "Intro"))
        doc.paragraphs[0].text = "Short." 
        normalizer_small = DocumentNormalizer(target_tokens=200, overlap_tokens=20)
        normalizer_large = DocumentNormalizer(target_tokens=2000, overlap_tokens=20)
        _, c_small = normalizer_small.normalize(doc, VERSION_UUID)
        _, c_large = normalizer_large.normalize(doc, VERSION_UUID)
        # Both should work; small target may produce more chunks
        assert len(c_small) >= 1
        assert len(c_large) >= 1
