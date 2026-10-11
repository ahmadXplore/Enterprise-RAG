"""PlainTextParser — zero-dependency parser for plain-text (.txt) documents.

Handles legal contracts and agreements stored as raw text files.
Detects ALL-CAPS headings, numbered section headings, and paragraph blocks.
No external library dependencies required.
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

# Patterns for headings
_ALLCAPS_HEADING = re.compile(r"^[A-Z][A-Z\s\d\.,\-\(\)&]{4,}$")
_NUMBERED_HEADING = re.compile(
    r"^(\d+\.(?:\d+\.)*)\s+([A-Z][A-Za-z\s\d\.,\-\(\)&]{2,})$"
)
_ARTICLE_HEADING = re.compile(
    r"^(ARTICLE|SECTION|EXHIBIT|SCHEDULE|ANNEX)\s+[\dIVXivx]+", re.IGNORECASE
)

_TEXT_PARSER_VERSION = "1.0.0"


class PlainTextParser(BaseParser):
    """Parse plain .txt files by splitting into headings and paragraphs.

    Heuristics applied in order:
    1. ALL-CAPS lines shorter than 120 chars  → heading (level 1 or 2)
    2. Lines matching ARTICLE/SECTION/EXHIBIT  → heading (level 1)
    3. Numbered section lines (1.2 Title)       → heading (level 2)
    4. Everything else                          → paragraph

    Pages are synthesised every 60 paragraphs to support page-based navigation.
    """

    @property
    def name(self) -> str:
        return "plain_text"

    @property
    def version(self) -> str:
        return _TEXT_PARSER_VERSION

    def parse(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Parse a plain-text file into a NormalizedDocument."""
        self._check_path(file_path)

        start = time.monotonic()

        # Try common encodings gracefully
        raw_text = _read_text(file_path)
        lines = raw_text.splitlines()

        if file_path.suffix.lower() == ".jsonl":
            headings, paragraphs, pages = self._parse_jsonl(lines)
        else:
            headings, paragraphs, pages = self._parse_lines(lines)
        duration = time.monotonic() - start

        return NormalizedDocument(
            document_id=document_id,
            document_version_id=document_version_id,
            pages=pages,
            headings=headings,
            paragraphs=paragraphs,
            tables=[],  # Plain-text files rarely contain structured tables
            provenance=ParserProvenance(
                parser_name=self.name,
                parser_version=self.version,
                duration_seconds=round(duration, 3),
                fallback_used=False,
                fallback_reason="",
            ),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_jsonl(
        self, lines: list[str]
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedPage]]:
        import json

        paragraphs: list[ParsedParagraph] = []
        reading_order = 0
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if isinstance(data, dict):
                    text = data.get("text") or data.get("clause") or data.get("content") or ""
                else:
                    text = str(data)
            except Exception:
                text = line_str

            text = text.strip()
            if len(text) > 10:
                paragraphs.append(
                    ParsedParagraph(
                        text=text,
                        page=None,
                        section_path="Clauses",
                        reading_order=reading_order,
                    )
                )
                reading_order += 1

        headings = [ParsedHeading(level=1, text="Clauses", page=None, path="Clauses")] if paragraphs else []
        return headings, paragraphs, []

    def _parse_lines(
        self, lines: list[str]
    ) -> tuple[list[ParsedHeading], list[ParsedParagraph], list[ParsedPage]]:
        headings: list[ParsedHeading] = []
        paragraphs: list[ParsedParagraph] = []
        heading_stack: list[tuple[int, str]] = []
        reading_order = 0
        paragraph_buf: list[str] = []

        def _flush_paragraph() -> None:
            nonlocal reading_order
            text = " ".join(paragraph_buf).strip()
            paragraph_buf.clear()
            if len(text) < 10:
                return
            paragraphs.append(
                ParsedParagraph(
                    text=text,
                    page=None,
                    section_path=_current_path(),
                    reading_order=reading_order,
                )
            )
            reading_order += 1

        def _current_path() -> str:
            return " > ".join(t for _, t in heading_stack)

        def _add_heading(level: int, text: str) -> None:
            _flush_paragraph()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, text))
            headings.append(
                ParsedHeading(level=level, text=text, page=None, path=_current_path())
            )

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                _flush_paragraph()
                continue

            # ARTICLE / SECTION / EXHIBIT headings → level 1
            if _ARTICLE_HEADING.match(line) and len(line) < 120:
                _add_heading(1, line)
                continue

            # ALL-CAPS heading → level 1 if short, else treat as paragraph
            if _ALLCAPS_HEADING.match(line) and len(line) < 100:
                _add_heading(1, line)
                continue

            # Numbered section heading → level 2
            m = _NUMBERED_HEADING.match(line)
            if m and len(line) < 100:
                _add_heading(2, line)
                continue

            # Normal text — accumulate into paragraph buffer
            paragraph_buf.append(line)

        _flush_paragraph()

        # Synthesise pages every 50 paragraphs
        pages: list[ParsedPage] = []
        per_page = 50
        total = len(paragraphs)
        for page_num, start_idx in enumerate(range(0, max(total, 1), per_page), start=1):
            batch = paragraphs[start_idx : start_idx + per_page]
            page_text = "\n".join(p.text for p in batch)
            pages.append(
                ParsedPage(
                    page_number=page_num,
                    text=page_text,
                    is_empty=not page_text.strip(),
                )
            )

        return headings, paragraphs, pages


def _read_text(path: Path) -> str:
    """Read a text file, trying UTF-8 then latin-1 as fallback."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    # Last resort: ignore bad chars
    return path.read_text(encoding="utf-8", errors="replace")
