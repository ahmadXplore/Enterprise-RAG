"""PDFParser — fast, high-fidelity PDF parser using PyMuPDF (fitz) or pypdf.

Extracts text, headings, paragraphs, and page structure from research papers and educational documents.
Produces NormalizedDocument conforming to the RAG ingestion pipeline contract.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedPage,
    ParsedParagraph,
    ParsedTable,
    ParserProvenance,
)
from packages.ingestion.parsers.base import BaseParser

_PDF_PARSER_VERSION = "1.0.0"

try:
    import pymupdf as fitz  # PyMuPDF
    _PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz
        _PYMUPDF_AVAILABLE = True
    except ImportError:
        _PYMUPDF_AVAILABLE = False

try:
    import pypdf
    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False


class PDFParser(BaseParser):
    """Parses PDF documents into structured NormalizedDocument representations."""

    @property
    def name(self) -> str:
        return "pymupdf_pdf"

    @property
    def version(self) -> str:
        return _PDF_PARSER_VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse a PDF file into a NormalizedDocument."""
        self._check_path(file_path)

        start = time.monotonic()
        pages: list[ParsedPage] = []
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        tables: list[ParsedTable] = []
        reading_order = 0

        if _PYMUPDF_AVAILABLE:
            doc = fitz.open(str(file_path))
            for page_idx, page in enumerate(doc, 1):
                page_text = page.get_text()
                pages.append(ParsedPage(page_number=page_idx, text=page_text, is_empty=not page_text.strip()))

                # Extract blocks
                blocks = page.get_text("blocks")
                current_section_path = ""
                for b in blocks:
                    text = b[4].strip()
                    if not text:
                        continue

                    # Filter out simple page numbers or small footer lines
                    if re.match(r"^(page\s+\d+|\d+\s+of\s+\d+|\d+)$", text, re.IGNORECASE):
                        continue

                    lines = text.split("\n")
                    first_line = lines[0].strip()

                    # Heading detection heuristics
                    is_heading = (
                        len(lines) == 1
                        and len(text) < 80
                        and (
                            re.match(r"^(abstract|introduction|background|methodology|methods|experiments|results|discussion|conclusion|references|related work)", text, re.IGNORECASE)
                            or re.match(r"^\d+(\.\d+)*\s+[A-Z]", text)
                            or (text.isupper() and len(text) > 3)
                        )
                    )

                    if is_heading:
                        level = 1 if re.match(r"^(\d+\s+[A-Z]|abstract|introduction|conclusion|references)", text, re.IGNORECASE) else 2
                        headings.append(
                            ParsedHeading(
                                level=level,
                                text=text,
                                page=page_idx,
                                path=text,
                            )
                        )
                        current_section_path = text
                    else:
                        reading_order += 1
                        paragraphs.append(
                            ParsedParagraph(
                                text=text,
                                page=page_idx,
                                section_path=current_section_path,
                                reading_order=reading_order,
                            )
                        )

            doc.close()
        elif _PYPDF_AVAILABLE:
            reader = pypdf.PdfReader(str(file_path))
            for page_idx, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                pages.append(ParsedPage(page_number=page_idx, text=text, is_empty=not text.strip()))
                paragraphs.append(
                    ParsedParagraph(
                        text=text,
                        page=page_idx,
                        section_path="",
                        reading_order=page_idx,
                    )
                )
        else:
            raise RuntimeError("Neither PyMuPDF nor pypdf is installed for PDF parsing.")

        duration = time.monotonic() - start

        return NormalizedDocument(
            document_id=document_id,
            document_version_id=document_version_id,
            pages=pages,
            headings=headings,
            paragraphs=paragraphs,
            tables=tables,
            provenance=ParserProvenance(
                parser_name=self.name,
                parser_version=self.version,
                duration_seconds=round(duration, 3),
                fallback_used=False,
                fallback_reason="",
            ),
        )
