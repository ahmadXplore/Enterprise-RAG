"""ParserDispatcher — selects the appropriate parser and writes parsed artifacts.

Selection order:
  1. DoclingParser (primary — supports PDF, DOCX, PPTX, HTML)
  2. HTMLSpecializedParser (for .html/.htm when Docling is unavailable)
  3. UnstructuredFallbackParser (all other cases)

After successful parsing, writes three artifacts to
``data/parsed/<document_id>/``:
  - document.json  — NormalizedDocument as JSON
  - document.html  — joined table HTML fragments
  - document.md    — Markdown summary (headings + paragraphs)

The original source file is never modified.
"""
from __future__ import annotations

import logging
from pathlib import Path

from packages.ingestion.parsed_document import NormalizedDocument
from packages.ingestion.parsers.docling_parser import _DOCLING_AVAILABLE, DoclingParser
from packages.ingestion.parsers.docx_parser import DocxParser
from packages.ingestion.parsers.html_parser import _BS4_AVAILABLE, HTMLSpecializedParser
from packages.ingestion.parsers.pdf_parser import PDFParser
from packages.ingestion.parsers.tabular_parser import TabularParser
from packages.ingestion.parsers.text_parser import PlainTextParser
from packages.ingestion.parsers.unstructured_parser import (
    _UNSTRUCTURED_AVAILABLE,
    UnstructuredFallbackParser,
)

logger = logging.getLogger(__name__)

_HTML_SUFFIXES = {".html", ".htm"}
_TEXT_SUFFIXES = {".txt", ".text", ".jsonl"}
_TABULAR_SUFFIXES = {".csv", ".xlsx", ".xlsm", ".xltx"}


class ParserDispatcher:
    """Dispatch parsing to the best available parser and write output artifacts."""

    def __init__(self, parsed_root: Path | None = None) -> None:
        """
        Args:
            parsed_root: Root directory for parsed output artifacts.
                Defaults to ``data/parsed/`` relative to cwd.
        """
        self._parsed_root = (parsed_root or Path("data/parsed")).resolve()
        self._docling = DoclingParser()
        self._pdf = PDFParser()
        self._docx = DocxParser()
        self._tabular = TabularParser()
        self._html = HTMLSpecializedParser()
        self._text = PlainTextParser()
        self._unstructured = UnstructuredFallbackParser()

    def dispatch(
        self,
        file_path: Path,
        document_id: str,
        document_version_id: str,
    ) -> NormalizedDocument:
        """Select the best parser, parse the file, and write artifacts."""
        suffix = file_path.suffix.lower()
        errors: list[str] = []

        # --- 1. Specialized PDF Parser ---
        if suffix == ".pdf":
            try:
                doc = self._pdf.parse(file_path, document_id, document_version_id)
                logger.info("PDFParser parsed '%s' in %.2fs", file_path.name, doc.provenance.duration_seconds)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"PDFParser error: {exc}")
                logger.warning("PDFParser failed for '%s': %s", file_path.name, exc)

        # --- 2. Specialized Word (DOCX) Parser ---
        if suffix in {".docx", ".doc"}:
            try:
                doc = self._docx.parse(file_path, document_id, document_version_id)
                logger.info("DocxParser parsed '%s' in %.2fs", file_path.name, doc.provenance.duration_seconds)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"DocxParser error: {exc}")
                logger.warning("DocxParser failed for '%s': %s", file_path.name, exc)

        # --- 3. Specialized Tabular (CSV / XLSX) Parser ---
        if suffix in _TABULAR_SUFFIXES:
            try:
                doc = self._tabular.parse(file_path, document_id, document_version_id)
                logger.info("TabularParser parsed '%s' in %.2fs", file_path.name, doc.provenance.duration_seconds)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"TabularParser error: {exc}")
                logger.warning("TabularParser failed for '%s': %s", file_path.name, exc)

        # --- 4. Docling (if available) ---
        if _DOCLING_AVAILABLE:
            try:
                doc = self._docling.parse(file_path, document_id, document_version_id)
                logger.info("Docling parsed '%s' in %.2fs", file_path.name, doc.provenance.duration_seconds)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"DoclingParser error: {exc}")
                logger.warning("Docling failed for '%s': %s", file_path.name, exc)

        # --- 5. HTML specialist (for HTML files) ---
        if suffix in _HTML_SUFFIXES and _BS4_AVAILABLE:
            try:
                doc = self._html.parse(file_path, document_id, document_version_id)
                logger.info("HTMLSpecializedParser parsed '%s'", file_path.name)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"HTMLSpecializedParser error: {exc}")
                logger.warning("HTML parser failed for '%s': %s", file_path.name, exc)

        # --- 6. Plain-text parser (for .txt / .text / .jsonl files) ---
        if suffix in _TEXT_SUFFIXES:
            try:
                doc = self._text.parse(file_path, document_id, document_version_id)
                logger.info("PlainTextParser parsed '%s'", file_path.name)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"PlainTextParser error: {exc}")
                logger.warning("PlainText parser failed for '%s': %s", file_path.name, exc)

        # --- 7. Unstructured fallback ---
        if _UNSTRUCTURED_AVAILABLE:
            try:
                fallback_reason = "; ".join(errors)
                doc = self._unstructured.parse(
                    file_path, document_id, document_version_id, fallback_reason=fallback_reason
                )
                logger.info("UnstructuredFallbackParser parsed '%s'", file_path.name)
                self._write_artifacts(doc, document_id)
                return doc
            except Exception as exc:
                errors.append(f"UnstructuredFallbackParser error: {exc}")
                logger.error("All parsers failed for '%s': %s", file_path.name, errors)

        raise RuntimeError(
            f"All parsers failed for '{file_path.name}'. Errors: {'; '.join(errors)}"
        )

    # ------------------------------------------------------------------
    # Artifact writing
    # ------------------------------------------------------------------

    def _write_artifacts(self, doc: NormalizedDocument, document_id: str) -> None:
        """Write document.json, document.html, document.md to parsed/<document_id>/."""
        out_dir = self._parsed_root / document_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # 1. document.json — full NormalizedDocument (lossless)
        (out_dir / "document.json").write_text(
            doc.model_dump_json(indent=2), encoding="utf-8"
        )

        # 2. document.html — all table HTML fragments joined
        table_fragments = "\n".join(t.table_html for t in doc.tables if t.table_html)
        html_body = f"<html><body>\n{table_fragments}\n</body></html>"
        (out_dir / "document.html").write_text(html_body, encoding="utf-8")

        # 3. document.md — heading + paragraph Markdown
        md_lines: list[str] = []
        for h in doc.headings:
            md_lines.append(f"{'#' * h.level} {h.text}\n")
        for p in doc.paragraphs:
            md_lines.append(f"{p.text}\n")
        (out_dir / "document.md").write_text("\n".join(md_lines), encoding="utf-8")

        logger.debug("Artifacts written to %s", out_dir)
