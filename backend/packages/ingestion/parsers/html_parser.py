"""HTMLSpecializedParser — targeted HTML parser using BeautifulSoup + lxml.

Used for HTML-only inputs.  Extracts headings (h1–h6), paragraphs, and
<table> elements with their full HTML preserved.
"""
from __future__ import annotations

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

try:
    from bs4 import BeautifulSoup  # type: ignore[import-untyped]

    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

_VERSION = "bs4+lxml"

# Tags treated as block paragraphs
_PARA_TAGS = {"p", "li", "dd", "blockquote", "pre"}
# Tags treated as headings
_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class HTMLSpecializedParser(BaseParser):
    """Parse HTML documents using BeautifulSoup with the lxml backend."""

    @property
    def name(self) -> str:
        return "html_specialized"

    @property
    def version(self) -> str:
        return _VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse an HTML file and return a NormalizedDocument.

        Args:
            file_path: Path to the .html file.
            document_id: UUID string of the Document row.
            document_version_id: UUID string of the DocumentVersion row.

        Raises:
            RuntimeError: If BeautifulSoup/lxml is not installed.
            ValueError: If the path is not an HTML file.
        """
        if not _BS4_AVAILABLE:
            raise RuntimeError(
                "beautifulsoup4 and lxml are required for HTMLSpecializedParser. "
                "Install them: pip install 'enterprise-rag[parsing]'"
            )

        self._check_path(file_path)

        if not file_path.is_file():
            raise ValueError(f"File does not exist: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in {".html", ".htm"}:
            raise ValueError(
                f"HTMLSpecializedParser only handles .html/.htm files, got: {file_path.name}"
            )

        start = time.monotonic()
        raw_html = file_path.read_text(encoding="utf-8", errors="replace")
        headings, paragraphs, tables, title = _parse_html(raw_html)
        duration = time.monotonic() - start

        # HTML documents are treated as single-page
        full_text = "\n".join(
            [h.text for h in headings]
            + [p.text for p in paragraphs]
            + [t.text for t in tables]
        )
        pages = [ParsedPage(page_number=1, text=full_text, is_empty=not full_text.strip())]

        return NormalizedDocument(
            document_id=document_id,
            document_version_id=document_version_id,
            title=title,
            pages=pages,
            headings=headings,
            paragraphs=paragraphs,
            tables=tables,
            provenance=ParserProvenance(
                parser_name=self.name,
                parser_version=self.version,
                duration_seconds=round(duration, 3),
                fallback_used=False,
            ),
        )

    def parse_string(
        self,
        html_content: str,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse raw HTML string directly (for in-memory/test use).

        No path-traversal check is needed because no file path is involved.
        """
        if not _BS4_AVAILABLE:
            raise RuntimeError(
                "beautifulsoup4 and lxml are required for HTMLSpecializedParser."
            )

        start = time.monotonic()
        headings, paragraphs, tables, title = _parse_html(html_content)
        duration = time.monotonic() - start

        full_text = "\n".join(
            [h.text for h in headings]
            + [p.text for p in paragraphs]
            + [t.text for t in tables]
        )
        pages = [ParsedPage(page_number=1, text=full_text, is_empty=not full_text.strip())]

        return NormalizedDocument(
            document_id=document_id,
            document_version_id=document_version_id,
            title=title,
            pages=pages,
            headings=headings,
            paragraphs=paragraphs,
            tables=tables,
            provenance=ParserProvenance(
                parser_name=self.name,
                parser_version=self.version,
                duration_seconds=round(duration, 3),
                fallback_used=False,
            ),
        )


# ------------------------------------------------------------------
# Module-level parse helper (pure function — easy to unit-test)
# ------------------------------------------------------------------

def _parse_html(
    raw_html: str,
) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedTable], str]:
    """Extract structured content from a raw HTML string.

    Returns (headings, paragraphs, tables, title).
    """
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(raw_html, "lxml")

    # Page title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    headings: list[ParsedHeading] = []
    paragraphs: list[ParsedParagraph] = []
    tables: list[ParsedTable] = []

    heading_stack: list[tuple[int, str]] = []

    def _current_path() -> str:
        return " > ".join(t for _, t in heading_stack)

    # IDs of Tag objects that are inside an already-processed table.
    inside_table: set[int] = set()
    reading_order = 0

    import re
    sec_item_re = re.compile(r"^(?:ITEM|PART)\s+[0-9A-Z]+[\.\:\s]?", re.IGNORECASE)

    body = soup.find("body") or soup

    for tag in body.find_all(True):
        if id(tag) in inside_table:
            continue

        style = tag.get("style", "")
        if "display:none" in str(style).lower():
            continue

        tag_name = tag.name.lower() if tag.name else ""

        if tag_name in _HEADING_TAGS:
            level = _HEADING_TAGS[tag_name]
            text = tag.get_text(separator=" ", strip=True)
            if not text:
                continue
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            headings.append(
                ParsedHeading(level=level, text=text, path=_current_path())
            )

        elif tag_name == "table":
            text = tag.get_text(separator=" ", strip=True)
            # Ignore empty spacer tables commonly used in SEC formatting
            if len(text) > 10:
                table_html = str(tag)
                row_count = len(tag.find_all("tr"))
                first_row = tag.find("tr")
                col_count = len(first_row.find_all(["td", "th"])) if first_row else 0
                caption_tag = tag.find("caption")
                caption = caption_tag.get_text(strip=True) if caption_tag else ""
                tables.append(
                    ParsedTable(
                        text=text,
                        table_html=table_html,
                        caption=caption,
                        section_path=_current_path(),
                        reading_order=reading_order,
                        row_count=row_count,
                        col_count=col_count,
                    )
                )
                reading_order += 1
            # Mark all descendants as processed so they are skipped
            for desc in tag.find_all(True):
                inside_table.add(id(desc))

        elif tag_name in _PARA_TAGS or (tag_name == "div" and not tag.find("div") and not tag.find("table")):
            text = tag.get_text(separator=" ", strip=True)
            if not text:
                continue

            # Detect SEC Item / Part headings in SEC filings
            if sec_item_re.match(text) and len(text) < 120:
                level = 1 if text.lower().startswith("part") else 2
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, text))
                headings.append(
                    ParsedHeading(level=level, text=text, path=_current_path())
                )
            elif len(text) > 20:
                paragraphs.append(
                    ParsedParagraph(
                        text=text,
                        section_path=_current_path(),
                        reading_order=reading_order,
                    )
                )
                reading_order += 1

    return headings, paragraphs, tables, title
