"""Normalized intermediate document representation produced by all parsers.

Every parser must return a NormalizedDocument regardless of source format.
This is the single internal contract between Phase 4 (parsing) and Phase 5 (chunking).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParsedPage(BaseModel):
    """One physical page of a document."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(..., ge=1)
    text: str = ""
    is_empty: bool = False


class ParsedHeading(BaseModel):
    """A section heading extracted in reading order."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(..., ge=1, le=6)
    text: str
    page: int | None = None
    # Materialized ancestor path, e.g. "Part I > Item 1 > Business"
    path: str = ""


class ParsedParagraph(BaseModel):
    """A body paragraph extracted in reading order."""

    model_config = ConfigDict(extra="forbid")

    text: str
    page: int | None = None
    # Heading path in effect when this paragraph was encountered
    section_path: str = ""
    reading_order: int = 0


class ParsedTable(BaseModel):
    """A table extracted from the document."""

    model_config = ConfigDict(extra="forbid")

    # Plain text representation (rows joined by newlines)
    text: str
    # Lossless HTML representation — must not be empty for real tables
    table_html: str
    caption: str = ""
    page: int | None = None
    section_path: str = ""
    reading_order: int = 0
    row_count: int = 0
    col_count: int = 0


class ParserProvenance(BaseModel):
    """Records which parser produced this document and how."""

    model_config = ConfigDict(extra="forbid")

    parser_name: str
    parser_version: str
    duration_seconds: float = 0.0
    # True when the primary parser failed and a fallback was used
    fallback_used: bool = False
    # Human-readable reason for fallback (if fallback_used)
    fallback_reason: str = ""


class NormalizedDocument(BaseModel):
    """Unified intermediate representation for one document version.

    Fields map directly to the TRD §5 normalized document model.
    All parsers must produce this structure.
    """

    model_config = ConfigDict(extra="forbid")

    # Identity (populated from DocumentVersion after registration)
    document_id: str
    document_version_id: str

    # Document-level metadata
    title: str = ""
    organization: str = ""
    report_year: int | None = None
    document_type: str = ""
    source_type: str = ""
    source_uri: str = ""
    content_hash: str = ""  # SHA-256 of the source file

    # Structural content (in reading order)
    pages: list[ParsedPage] = Field(default_factory=list)
    headings: list[ParsedHeading] = Field(default_factory=list)
    paragraphs: list[ParsedParagraph] = Field(default_factory=list)
    tables: list[ParsedTable] = Field(default_factory=list)

    # Parser metadata
    provenance: ParserProvenance

    # Catch-all for parser-specific extras that don't fit above
    extra: dict[str, Any] = Field(default_factory=dict)
