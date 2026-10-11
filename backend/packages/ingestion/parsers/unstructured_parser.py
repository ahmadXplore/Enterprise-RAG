"""UnstructuredFallbackParser — secondary parser using the Unstructured library.

Used only when DoclingParser fails or is unavailable for the given file type.
Maps Unstructured element types to the NormalizedDocument model.
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

_UNSTRUCTURED_VERSION = "unknown"

try:
    import unstructured  # type: ignore[import-untyped]
    from unstructured.partition.auto import partition  # type: ignore[import-untyped]

    _UNSTRUCTURED_VERSION = getattr(unstructured, "__version__", ">=0.14")
    _UNSTRUCTURED_AVAILABLE = True
except ImportError:
    _UNSTRUCTURED_AVAILABLE = False


class UnstructuredFallbackParser(BaseParser):
    """Parse documents using Unstructured as a fallback when Docling is unavailable."""

    @property
    def name(self) -> str:
        return "unstructured"

    @property
    def version(self) -> str:
        return _UNSTRUCTURED_VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
        fallback_reason: str = "",
    ) -> NormalizedDocument:
        """Parse *file_path* via Unstructured.

        Raises:
            RuntimeError: If Unstructured is not installed.
            RuntimeError: If partitioning fails.
        """
        if not _UNSTRUCTURED_AVAILABLE:
            raise RuntimeError(
                "Unstructured is not installed. Install the 'parsing' extras: "
                "pip install 'enterprise-rag[parsing]'"
            )

        self._check_path(file_path)

        if not file_path.is_file():
            raise ValueError(f"File does not exist: {file_path}")

        start = time.monotonic()

        try:
            elements = partition(filename=str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Unstructured partitioning failed for '{file_path.name}': {exc}"
            ) from exc

        duration = time.monotonic() - start

        headings, paragraphs, tables, pages = self._map_elements(elements)

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
                fallback_used=True,
                fallback_reason=fallback_reason,
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _map_elements(
        self, elements: list
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedTable], list[ParsedPage]]:
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        tables: list[ParsedTable] = []
        page_texts: dict[int, list[str]] = {}
        heading_stack: list[tuple[int, str]] = []
        reading_order = 0

        def _current_path() -> str:
            return " > ".join(t for _, t in heading_stack)

        for el in elements:
            type_name = type(el).__name__

            page_no: int | None = None
            try:
                meta = el.metadata
                page_no = getattr(meta, "page_number", None)
                if page_no is not None:
                    page_no = int(page_no)
            except (AttributeError, TypeError, ValueError):
                pass

            text = str(el).strip()
            if not text:
                continue

            if page_no is not None:
                page_texts.setdefault(page_no, []).append(text)

            if "Title" in type_name or "Header" in type_name:
                level = 1 if "Title" in type_name else 2
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, text))
                headings.append(
                    ParsedHeading(level=level, text=text, page=page_no, path=_current_path())
                )

            elif "Table" in type_name:
                table_html = _build_table_html(el)
                tables.append(
                    ParsedTable(
                        text=text,
                        table_html=table_html,
                        page=page_no,
                        section_path=_current_path(),
                        reading_order=reading_order,
                    )
                )
                reading_order += 1

            else:
                paragraphs.append(
                    ParsedParagraph(
                        text=text,
                        page=page_no,
                        section_path=_current_path(),
                        reading_order=reading_order,
                    )
                )
                reading_order += 1

        pages = [
            ParsedPage(
                page_number=pno,
                text="\n".join(texts),
                is_empty=not any(t.strip() for t in texts),
            )
            for pno, texts in sorted(page_texts.items())
        ]

        return headings, paragraphs, tables, pages


def _build_table_html(element: object) -> str:
    """Build a minimal HTML table from an Unstructured Table element."""
    try:
        html_table = element.metadata.text_as_html  # type: ignore[union-attr]
        if html_table:
            return str(html_table)
    except AttributeError:
        pass

    # Fallback: render rows from element text (tab/newline delimited)
    text = str(element).strip()
    if not text:
        return "<table></table>"

    rows_html = []
    for line in text.splitlines():
        cells = line.split("\t") if "\t" in line else [line]
        cells_html = "".join(f"<td>{c.strip()}</td>" for c in cells)
        rows_html.append(f"<tr>{cells_html}</tr>")

    return f"<table>{''.join(rows_html)}</table>"
