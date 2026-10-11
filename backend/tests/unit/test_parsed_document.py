import pytest
from pydantic import ValidationError

from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedPage,
    ParsedParagraph,
    ParsedTable,
    ParserProvenance,
)


def _minimal_doc(**kwargs) -> NormalizedDocument:
    defaults = dict(
        document_id="doc-1",
        document_version_id="ver-1",
        provenance=ParserProvenance(parser_name="test", parser_version="0.1"),
    )
    defaults.update(kwargs)
    return NormalizedDocument(**defaults)


class TestParsedPage:
    def test_valid(self):
        page = ParsedPage(page_number=1, text="Hello world")
        assert page.page_number == 1
        assert not page.is_empty

    def test_empty_flag(self):
        page = ParsedPage(page_number=2, text="", is_empty=True)
        assert page.is_empty

    def test_page_number_must_be_positive(self):
        with pytest.raises(ValidationError):
            ParsedPage(page_number=0)


class TestParsedHeading:
    def test_valid(self):
        h = ParsedHeading(level=2, text="Revenue", page=5, path="Part I > Revenue")
        assert h.level == 2
        assert h.path == "Part I > Revenue"

    def test_level_bounds(self):
        with pytest.raises(ValidationError):
            ParsedHeading(level=0, text="Bad")
        with pytest.raises(ValidationError):
            ParsedHeading(level=7, text="Bad")


class TestParsedTable:
    def test_requires_table_html(self):
        tbl = ParsedTable(
            text="A B\n1 2",
            table_html="<table><tr><td>A</td><td>B</td></tr></table>",
            row_count=2,
            col_count=2,
        )
        assert tbl.table_html.startswith("<table")

    def test_empty_table_html_allowed_in_model(self):
        # Parser may produce empty table_html — quality report counts it as failure
        tbl = ParsedTable(text="", table_html="")
        assert tbl.table_html == ""


class TestNormalizedDocument:
    def test_minimal_construction(self):
        doc = _minimal_doc()
        assert doc.document_id == "doc-1"
        assert doc.pages == []
        assert doc.headings == []
        assert doc.paragraphs == []
        assert doc.tables == []

    def test_with_all_fields(self):
        provenance = ParserProvenance(
            parser_name="docling",
            parser_version="2.36.1",
            duration_seconds=1.5,
            fallback_used=False,
        )
        doc = NormalizedDocument(
            document_id="abc",
            document_version_id="ver-abc",
            title="Annual Report 2024",
            organization="Acme Corp",
            report_year=2024,
            document_type="annual_report",
            source_type="sec",
            content_hash="a" * 64,
            pages=[ParsedPage(page_number=1, text="cover")],
            headings=[ParsedHeading(level=1, text="Part I")],
            paragraphs=[ParsedParagraph(text="Our revenue grew.", page=1)],
            tables=[
                ParsedTable(
                    text="Q1 Q2",
                    table_html="<table><tr><td>Q1</td><td>Q2</td></tr></table>",
                    row_count=1,
                    col_count=2,
                )
            ],
            provenance=provenance,
        )
        assert doc.title == "Annual Report 2024"
        assert len(doc.pages) == 1
        assert len(doc.tables) == 1

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedDocument(
                document_id="x",
                document_version_id="y",
                provenance=ParserProvenance(parser_name="t", parser_version="0"),
                unknown_field="oops",  # extra='forbid'
            )

    def test_provenance_fallback_fields(self):
        prov = ParserProvenance(
            parser_name="unstructured",
            parser_version="0.14",
            fallback_used=True,
            fallback_reason="Docling ImportError",
        )
        assert prov.fallback_used is True
        assert "Docling" in prov.fallback_reason
