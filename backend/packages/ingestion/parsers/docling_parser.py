"""DoclingParser — primary document parser using the Docling library.

Docling supports PDF, DOCX, PPTX, HTML and other formats with structure-aware
extraction (tables, headings, reading order).  It is the preferred parser for
all document types in this system.

If Docling is not installed (optional dependency group 'parsing'), this parser
raises RuntimeError with a clear installation message so the dispatcher can
fall back gracefully.
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

_DOCLING_VERSION = "unknown"

try:
    import docling  # type: ignore[import-untyped]
    from docling.datamodel.document import ConversionResult  # type: ignore[import-untyped]
    from docling.document_converter import DocumentConverter  # type: ignore[import-untyped]

    _DOCLING_VERSION = getattr(docling, "__version__", ">=2.0")
    _DOCLING_AVAILABLE = True
except ImportError:
    _DOCLING_AVAILABLE = False


class DoclingParser(BaseParser):
    """Parse documents using Docling as the primary engine."""

    @property
    def name(self) -> str:
        return "docling"

    @property
    def version(self) -> str:
        return _DOCLING_VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse *file_path* via Docling.

        Raises:
            RuntimeError: If Docling is not installed.
            RuntimeError: If Docling conversion fails.
        """
        if not _DOCLING_AVAILABLE:
            raise RuntimeError(
                "Docling is not installed. Install the 'parsing' extras: "
                "pip install 'enterprise-rag[parsing]'"
            )

        self._check_path(file_path)

        if not file_path.is_file():
            raise ValueError(f"File does not exist: {file_path}")

        start = time.monotonic()

        try:
            converter = DocumentConverter()
            result: ConversionResult = converter.convert(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Docling conversion failed for '{file_path.name}': {exc}") from exc

        doc = result.document
        duration = time.monotonic() - start

        pages = self._extract_pages(doc)
        headings, paragraphs, tables = self._extract_elements(doc)

        return NormalizedDocument(
            document_id=document_id,
            document_version_id=document_version_id,
            title=self._extract_title(doc),
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
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_title(self, doc: object) -> str:
        """Return the document title from Docling metadata if available."""
        try:
            return str(doc.name or "")  # type: ignore[union-attr]
        except AttributeError:
            return ""

    def _extract_pages(self, doc: object) -> list[ParsedPage]:
        """Convert Docling page objects to ParsedPage list."""
        pages: list[ParsedPage] = []
        try:
            for page in doc.pages.values():  # type: ignore[union-attr]
                page_no = int(page.page_no)
                text = page.export_to_markdown() if hasattr(page, "export_to_markdown") else ""
                pages.append(
                    ParsedPage(
                        page_number=page_no,
                        text=text,
                        is_empty=not text.strip(),
                    )
                )
        except AttributeError:
            pass
        return sorted(pages, key=lambda p: p.page_number)

    def _extract_elements(
        self, doc: object
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedTable]]:
        """Walk the Docling element tree in reading order."""
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        tables: list[ParsedTable] = []

        # Track the current heading stack to build materialized paths
        heading_stack: list[tuple[int, str]] = []  # (level, text)
        reading_order = 0

        def _current_path() -> str:
            return " > ".join(text for _, text in heading_stack)

        def _update_stack(level: int, text: str) -> None:
            # Pop headings of equal or deeper level
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))

        try:
            for element, _level in doc.iterate_items():  # type: ignore[union-attr]
                label = getattr(element, "label", None)
                if label is None:
                    continue

                label_str = str(label).lower()

                # --- Headings ---
                if "section_header" in label_str or "title" in label_str:
                    heading_level = _infer_heading_level(element)
                    text = _element_text(element)
                    if not text:
                        continue
                    _update_stack(heading_level, text)
                    page = _element_page(element)
                    headings.append(
                        ParsedHeading(
                            level=heading_level,
                            text=text,
                            page=page,
                            path=_current_path(),
                        )
                    )

                # --- Tables ---
                elif "table" in label_str:
                    page = _element_page(element)
                    text = _element_text(element)
                    table_html = _table_html(element)
                    row_count, col_count = _table_dimensions(element)
                    tables.append(
                        ParsedTable(
                            text=text,
                            table_html=table_html,
                            page=page,
                            section_path=_current_path(),
                            reading_order=reading_order,
                            row_count=row_count,
                            col_count=col_count,
                        )
                    )
                    reading_order += 1

                # --- Paragraphs / text ---
                elif "text" in label_str or "paragraph" in label_str or "list_item" in label_str:
                    text = _element_text(element)
                    if not text.strip():
                        continue
                    page = _element_page(element)
                    paragraphs.append(
                        ParsedParagraph(
                            text=text,
                            page=page,
                            section_path=_current_path(),
                            reading_order=reading_order,
                        )
                    )
                    reading_order += 1

        except (AttributeError, TypeError):
            # Docling API surface can vary; degrade gracefully rather than crash
            pass

        return headings, paragraphs, tables


# ------------------------------------------------------------------
# Module-level helpers (no self dependency — keep them small)
# ------------------------------------------------------------------

def _element_text(element: object) -> str:
    """Best-effort text extraction from a Docling element."""
    for attr in ("text", "export_to_markdown", "export_to_text"):
        val = getattr(element, attr, None)
        if val is None:
            continue
        if callable(val):
            try:
                return str(val())
            except Exception:  # noqa: BLE001, S112
                continue
        return str(val)
    return ""


def _element_page(element: object) -> int | None:
    """Extract a 1-based page number from a Docling element."""
    try:
        prov = element.prov  # type: ignore[union-attr]
        if prov:
            return int(prov[0].page_no)
    except (AttributeError, IndexError, TypeError):
        pass
    return None


def _table_html(element: object) -> str:
    """Export a Docling table element as HTML string."""
    for method in ("export_to_html", "to_html"):
        fn = getattr(element, method, None)
        if callable(fn):
            try:
                result = fn()
                if result:
                    return str(result)
            except Exception:  # noqa: BLE001, S112
                continue

    # Fallback: build minimal HTML from Docling TableCell grid
    try:
        data = element.data  # type: ignore[union-attr]
        rows_html = []
        for row in data.grid:
            cells_html = "".join(
                f"<td>{cell.text}</td>" for cell in row
            )
            rows_html.append(f"<tr>{cells_html}</tr>")
        return f"<table>{''.join(rows_html)}</table>"
    except (AttributeError, TypeError):
        return "<table></table>"


def _table_dimensions(element: object) -> tuple[int, int]:
    """Return (row_count, col_count) from a Docling table element."""
    try:
        data = element.data  # type: ignore[union-attr]
        return int(data.num_rows), int(data.num_cols)
    except (AttributeError, TypeError):
        return 0, 0


def _infer_heading_level(element: object) -> int:
    """Infer heading level (1–6) from Docling element properties."""
    # Some Docling versions expose a 'level' attribute on headings
    try:
        level = int(element.level)  # type: ignore[union-attr]
        return max(1, min(6, level))
    except (AttributeError, TypeError, ValueError):
        pass
    # Fall back to label name heuristics (e.g. "section_header_1")
    label = str(getattr(element, "label", ""))
    for ch in label:
        if ch.isdigit():
            return max(1, min(6, int(ch)))
    return 2  # default: treat as h2
