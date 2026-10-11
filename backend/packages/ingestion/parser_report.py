"""ParserQualityReport — counts structural elements in a NormalizedDocument.

Provides a fast quality gate: if a document parses to zero paragraphs,
zero pages, or many extraction failures, something likely went wrong.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from packages.ingestion.parsed_document import NormalizedDocument


class ParserQualityReport(BaseModel):
    """Counts of structural elements produced by a parser run."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    document_version_id: str
    parser_name: str
    parser_version: str
    fallback_used: bool = False

    page_count: int = 0
    empty_page_count: int = 0
    section_count: int = 0
    paragraph_count: int = 0
    table_count: int = 0
    extraction_failures: int = 0

    # True when the document appears to have extracted no useful content
    @property
    def is_empty_extraction(self) -> bool:
        return self.paragraph_count == 0 and self.table_count == 0 and self.section_count == 0


def build_report(doc: NormalizedDocument) -> ParserQualityReport:
    """Build a quality report from a NormalizedDocument.

    extraction_failures counts:
    - Tables with empty table_html
    - Paragraphs with empty text
    - Headings with empty text
    """
    failures = (
        sum(1 for t in doc.tables if not t.table_html or not t.table_html.strip())
        + sum(1 for p in doc.paragraphs if not p.text.strip())
        + sum(1 for h in doc.headings if not h.text.strip())
    )

    return ParserQualityReport(
        document_id=doc.document_id,
        document_version_id=doc.document_version_id,
        parser_name=doc.provenance.parser_name,
        parser_version=doc.provenance.parser_version,
        fallback_used=doc.provenance.fallback_used,
        page_count=len(doc.pages),
        empty_page_count=sum(1 for p in doc.pages if p.is_empty),
        section_count=len(doc.headings),
        paragraph_count=len(doc.paragraphs),
        table_count=len(doc.tables),
        extraction_failures=failures,
    )
