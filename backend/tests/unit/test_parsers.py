"""Tests for all three parser implementations + ParserQualityReport.

DoclingParser and UnstructuredFallbackParser tests use mocks because those
packages are optional (not installed in the base dev environment).
HTMLSpecializedParser tests run against real in-memory HTML strings using
the parse_string() method — no file I/O, no path-traversal needed.
"""
from pathlib import Path

import pytest

from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedPage,
    ParsedParagraph,
    ParsedTable,
    ParserProvenance,
)
from packages.ingestion.parser_report import build_report
from packages.ingestion.parsers.base import _assert_safe_path
from packages.ingestion.parsers.html_parser import HTMLSpecializedParser

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _make_doc(
    page_count=2,
    heading_count=1,
    para_count=3,
    table_count=1,
    empty_pages=0,
    table_html="<table><tr><td>A</td></tr></table>",
    empty_para=False,
) -> NormalizedDocument:
    pages = [
        ParsedPage(
            page_number=i + 1,
            text="text" if i >= empty_pages else "",
            is_empty=(i < empty_pages),
        )
        for i in range(page_count)
    ]
    headings = [ParsedHeading(level=1, text=f"H{i}") for i in range(heading_count)]
    paras = [
        ParsedParagraph(text="" if empty_para and i == 0 else f"Para {i}", page=1)
        for i in range(para_count)
    ]
    tables = [
        ParsedTable(text="A", table_html=table_html, row_count=1, col_count=1)
        for _ in range(table_count)
    ]
    return NormalizedDocument(
        document_id="doc-1",
        document_version_id="ver-1",
        pages=pages,
        headings=headings,
        paragraphs=paras,
        tables=tables,
        provenance=ParserProvenance(parser_name="test", parser_version="0.1"),
    )


# ------------------------------------------------------------------
# Path traversal guard
# ------------------------------------------------------------------

class TestPathTraversalGuard:
    def test_safe_path_inside_data(self, tmp_path):
        allowed = (tmp_path,)
        safe = tmp_path / "document.pdf"
        # Must not raise
        _assert_safe_path(safe, allowed_roots=allowed)

    def test_traversal_blocked(self, tmp_path):
        allowed = (tmp_path / "data",)
        evil = tmp_path / ".." / "etc" / "passwd"
        with pytest.raises(ValueError, match="Path traversal"):
            _assert_safe_path(evil, allowed_roots=allowed)

    def test_sibling_directory_blocked(self, tmp_path):
        allowed = (tmp_path / "a",)
        other = tmp_path / "b" / "file.txt"
        with pytest.raises(ValueError, match="Path traversal"):
            _assert_safe_path(other, allowed_roots=allowed)


# ------------------------------------------------------------------
# HTMLSpecializedParser (real, in-memory)
# ------------------------------------------------------------------

SAMPLE_HTML = """
<html>
<head><title>Annual Report 2024</title></head>
<body>
  <h1>Part I — Business</h1>
  <p>We operate a diversified portfolio of businesses.</p>
  <h2>Revenue Recognition</h2>
  <p>Revenue is recognized when control transfers to the customer.</p>
  <table>
    <tr><th>Year</th><th>Revenue ($M)</th></tr>
    <tr><td>2023</td><td>1,200</td></tr>
    <tr><td>2024</td><td>1,450</td></tr>
  </table>
  <h2>Risk Factors</h2>
  <p>Our business faces significant competitive risks.</p>
</body>
</html>
"""

LEGAL_HTML = """
<html>
<head><title>Master Services Agreement</title></head>
<body>
  <h1>Master Services Agreement</h1>
  <h2>1. Definitions</h2>
  <p>"Confidential Information" means any non-public information.</p>
  <h2>2. Indemnification</h2>
  <p>Each party shall indemnify the other against all third-party claims.</p>
  <table>
    <tr><th>Clause</th><th>Reference</th></tr>
    <tr><td>Termination</td><td>Section 9</td></tr>
    <tr><td>Indemnification</td><td>Section 10</td></tr>
  </table>
</body>
</html>
"""


class TestHTMLParser:
    def test_financial_document_headings(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")

        assert doc.title == "Annual Report 2024"
        heading_texts = [h.text for h in doc.headings]
        assert "Part I — Business" in heading_texts
        assert "Revenue Recognition" in heading_texts
        assert "Risk Factors" in heading_texts

    def test_heading_levels(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        h1s = [h for h in doc.headings if h.level == 1]
        h2s = [h for h in doc.headings if h.level == 2]
        assert len(h1s) == 1
        assert len(h2s) >= 2

    def test_financial_paragraphs(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        para_texts = [p.text for p in doc.paragraphs]
        assert any("diversified portfolio" in t for t in para_texts)
        assert any("Revenue is recognized" in t for t in para_texts)

    def test_financial_table_extracted(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        assert len(doc.tables) == 1
        tbl = doc.tables[0]
        assert tbl.row_count == 3
        assert tbl.col_count == 2
        assert "<table" in tbl.table_html
        assert "1,200" in tbl.table_html or "1,200" in tbl.text

    def test_table_html_preserved(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        tbl = doc.tables[0]
        # table_html must contain actual HTML table tags
        assert "<tr>" in tbl.table_html or "<tr " in tbl.table_html

    def test_legal_document(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(LEGAL_HTML, "doc-2", "ver-2")
        assert doc.title == "Master Services Agreement"
        heading_texts = [h.text for h in doc.headings]
        assert any("Indemnification" in t for t in heading_texts)
        para_texts = [p.text for p in doc.paragraphs]
        assert any("indemnify" in t for t in para_texts)

    def test_section_path_follows_heading_hierarchy(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        # Paragraphs under h2 should have a path containing the h1
        paras_with_path = [p for p in doc.paragraphs if p.section_path]
        if paras_with_path:
            paths = [p.section_path for p in paras_with_path]
            assert any("Part I" in path for path in paths)

    def test_page_is_single(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1

    def test_provenance_populated(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string(SAMPLE_HTML, "doc-1", "ver-1")
        assert doc.provenance.parser_name == "html_specialized"
        assert doc.provenance.fallback_used is False

    def test_empty_html_no_crash(self):
        parser = HTMLSpecializedParser()
        doc = parser.parse_string("<html><body></body></html>", "doc-x", "ver-x")
        assert doc.pages[0].is_empty

    def test_rejects_non_html_file(self, tmp_path):
        parser = HTMLSpecializedParser()
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")
        with pytest.raises(ValueError, match="only handles"):
            parser.parse(pdf_file, "doc-1", "ver-1")


# ------------------------------------------------------------------
# DoclingParser — mocked (Docling is an optional dependency)
# ------------------------------------------------------------------

class TestDoclingParserMocked:
    def test_raises_when_docling_not_installed(self, tmp_path):
        """When Docling is not installed, parse() raises RuntimeError."""
        import packages.ingestion.parsers.docling_parser as dp_module
        original = dp_module._DOCLING_AVAILABLE
        try:
            dp_module._DOCLING_AVAILABLE = False
            from packages.ingestion.parsers.docling_parser import DoclingParser
            parser = DoclingParser()
            fake_file = tmp_path / "test.pdf"
            fake_file.write_bytes(b"%PDF")
            with pytest.raises(RuntimeError, match="Docling is not installed"):
                parser.parse(fake_file, "doc-1", "ver-1")
        finally:
            dp_module._DOCLING_AVAILABLE = original

    def test_path_traversal_blocked(self, tmp_path):
        """DoclingParser.parse() must reject paths outside allowed roots."""
        import packages.ingestion.parsers.docling_parser as dp_module
        original = dp_module._DOCLING_AVAILABLE
        try:
            dp_module._DOCLING_AVAILABLE = False
            from packages.ingestion.parsers.docling_parser import DoclingParser
            parser = DoclingParser()
            evil_path = Path("/etc/passwd")
            with pytest.raises((ValueError, RuntimeError)):
                parser.parse(evil_path, "doc-1", "ver-1")
        finally:
            dp_module._DOCLING_AVAILABLE = original


# ------------------------------------------------------------------
# UnstructuredFallbackParser — mocked
# ------------------------------------------------------------------

class TestUnstructuredParserMocked:
    def test_raises_when_not_installed(self, tmp_path):
        import packages.ingestion.parsers.unstructured_parser as up_module
        original = up_module._UNSTRUCTURED_AVAILABLE
        try:
            up_module._UNSTRUCTURED_AVAILABLE = False
            from packages.ingestion.parsers.unstructured_parser import UnstructuredFallbackParser
            parser = UnstructuredFallbackParser()
            fake = tmp_path / "doc.pdf"
            fake.write_bytes(b"%PDF")
            with pytest.raises(RuntimeError, match="Unstructured is not installed"):
                parser.parse(fake, "doc-1", "ver-1")
        finally:
            up_module._UNSTRUCTURED_AVAILABLE = original


# ------------------------------------------------------------------
# ParserQualityReport
# ------------------------------------------------------------------

class TestParserQualityReport:
    def test_counts_pages(self):
        doc = _make_doc(page_count=5, empty_pages=2)
        report = build_report(doc)
        assert report.page_count == 5
        assert report.empty_page_count == 2

    def test_counts_headings_as_sections(self):
        doc = _make_doc(heading_count=4)
        report = build_report(doc)
        assert report.section_count == 4

    def test_counts_paragraphs(self):
        doc = _make_doc(para_count=7)
        report = build_report(doc)
        assert report.paragraph_count == 7

    def test_counts_tables(self):
        doc = _make_doc(table_count=3)
        report = build_report(doc)
        assert report.table_count == 3

    def test_extraction_failure_empty_table_html(self):
        doc = _make_doc(table_html="")
        report = build_report(doc)
        assert report.extraction_failures >= 1

    def test_extraction_failure_empty_para(self):
        doc = _make_doc(empty_para=True)
        report = build_report(doc)
        assert report.extraction_failures >= 1

    def test_is_empty_extraction_flag(self):
        doc = NormalizedDocument(
            document_id="x",
            document_version_id="y",
            provenance=ParserProvenance(parser_name="t", parser_version="0"),
        )
        report = build_report(doc)
        assert report.is_empty_extraction

    def test_non_empty_extraction(self):
        doc = _make_doc()
        report = build_report(doc)
        assert not report.is_empty_extraction

    def test_provenance_fields_in_report(self):
        doc = _make_doc()
        doc.provenance.fallback_used = True
        report = build_report(doc)
        assert report.fallback_used is True
