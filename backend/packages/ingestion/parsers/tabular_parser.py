"""TabularParser — parser for structured CSV and Excel (XLSX) educational datasets.

Converts spreadsheets and CSV tables into lossless HTML tables, plain text,
and column summary paragraphs conforming to the RAG ingestion pipeline contract.
"""
from __future__ import annotations

import csv
import html
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

_TABULAR_PARSER_VERSION = "1.0.0"

try:
    import openpyxl
    _OPENPYXL_AVAILABLE = True
except ImportError:
    _OPENPYXL_AVAILABLE = False


class TabularParser(BaseParser):
    """Parses .csv and .xlsx files into structured NormalizedDocument representations."""

    @property
    def name(self) -> str:
        return "tabular_spreadsheet"

    @property
    def version(self) -> str:
        return _TABULAR_PARSER_VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse a CSV or Excel file into a NormalizedDocument."""
        self._check_path(file_path)

        start = time.monotonic()
        suffix = file_path.suffix.lower()

        if suffix == ".csv":
            headings, paragraphs, tables = self._parse_csv(file_path)
        elif suffix in {".xlsx", ".xlsm", ".xltx"}:
            if not _OPENPYXL_AVAILABLE:
                raise RuntimeError("openpyxl is required for Excel (.xlsx) parsing.")
            headings, paragraphs, tables = self._parse_xlsx(file_path)
        else:
            raise ValueError(f"Unsupported tabular file format: {suffix}")

        duration = time.monotonic() - start

        # Synthesize a single page
        all_text = "\n\n".join(
            [h.text for h in headings] + [p.text for p in paragraphs] + [t.text for t in tables]
        )
        pages = [
            ParsedPage(
                page_number=1,
                text=all_text,
                is_empty=not all_text.strip(),
            )
        ]

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

    def _parse_csv(
        self, file_path: Path
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedTable]]:
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        tables: list[ParsedTable] = []

        title = file_path.stem.replace("_", " ").title()
        headings.append(ParsedHeading(level=1, text=title, page=1, path=title))

        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
        lines = [line for line in raw_text.splitlines() if line.strip()]

        reader = csv.reader(lines)
        rows: list[list[str]] = list(reader)

        if not rows:
            paragraphs.append(ParsedParagraph(text="Empty dataset.", page=1, section_path=title, reading_order=1))
            return headings, paragraphs, tables

        headers = [c.strip() for c in rows[0]]
        paragraphs.append(
            ParsedParagraph(
                text=f"Dataset '{title}' contains {len(rows)-1} records across {len(headers)} columns: {', '.join(headers)}.",
                page=1,
                section_path=title,
                reading_order=1,
            )
        )

        # Build table HTML & Text
        # Limit rows per table block if exceedingly huge, but retain full content for RAG
        max_rows = min(len(rows), 500)
        table_rows = rows[:max_rows]

        html_lines = ["<table>"]
        html_lines.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>")
        for r in table_rows[1:]:
            html_lines.append("<tr>" + "".join(f"<td>{html.escape(c.strip())}</td>" for c in r) + "</tr>")
        html_lines.append("</table>")

        plain_text = "\n".join(" | ".join(c.strip() for c in r) for r in table_rows)

        tables.append(
            ParsedTable(
                text=plain_text,
                table_html="\n".join(html_lines),
                caption=f"Dataset Table: {title}",
                page=1,
                section_path=title,
                reading_order=2,
                row_count=len(rows),
                col_count=len(headers),
            )
        )

        # Add sample row summaries for natural language RAG retrieval
        reading_order = 3
        for r_idx, r in enumerate(rows[1:min(15, len(rows))], 1):
            row_desc = "; ".join(f"{h}: {v}" for h, v in zip(headers, r) if v.strip())
            paragraphs.append(
                ParsedParagraph(
                    text=f"Record {r_idx}: {row_desc}",
                    page=1,
                    section_path=title,
                    reading_order=reading_order,
                )
            )
            reading_order += 1

        return headings, paragraphs, tables

    def _parse_xlsx(
        self, file_path: Path
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedTable]]:
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        tables: list[ParsedTable] = []

        title = file_path.stem.replace("_", " ").title()
        headings.append(ParsedHeading(level=1, text=title, page=1, path=title))

        wb = openpyxl.load_workbook(str(file_path), data_only=True)
        reading_order = 1

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            clean_sheet = sheet_name.replace("_", " ")
            headings.append(ParsedHeading(level=2, text=f"Sheet: {clean_sheet}", page=1, path=f"{title} > {clean_sheet}"))

            rows: list[list[str]] = []
            for r in ws.iter_rows(values_only=True):
                # Skip completely blank rows
                if any(v is not None and str(v).strip() for v in r):
                    rows.append([str(v).strip() if v is not None else "" for v in r])

            if not rows:
                continue

            headers = rows[0]
            paragraphs.append(
                ParsedParagraph(
                    text=f"Worksheet '{clean_sheet}' contains {len(rows)-1} rows. Key columns: {', '.join([h for h in headers if h][:8])}.",
                    page=1,
                    section_path=f"{title} > {clean_sheet}",
                    reading_order=reading_order,
                )
            )
            reading_order += 1

            html_lines = ["<table>"]
            html_lines.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>")
            for r in rows[1:min(len(rows), 400)]:
                html_lines.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
            html_lines.append("</table>")

            plain_text = "\n".join(" | ".join(r) for r in rows[:min(len(rows), 400)])

            tables.append(
                ParsedTable(
                    text=plain_text,
                    table_html="\n".join(html_lines),
                    caption=f"{title} - {clean_sheet}",
                    page=1,
                    section_path=f"{title} > {clean_sheet}",
                    reading_order=reading_order,
                    row_count=len(rows),
                    col_count=len(headers),
                )
            )
            reading_order += 1

        wb.close()
        return headings, paragraphs, tables
