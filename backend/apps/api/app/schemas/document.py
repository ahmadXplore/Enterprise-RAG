"""Pydantic schemas for Document and Chunk operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1)
    organization: str | None = None
    ticker: str | None = None
    report_year: int | None = None
    source_uri: str | None = None
    content_hash: str = Field(..., min_length=64, max_length=64)
    language: str | None = "en"


class DocumentRead(BaseModel):
    """Minimal document metadata for list operations."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_type: str
    document_type: str
    organization: str | None = None
    ticker: str | None = None
    report_year: int | None = None
    status: str
    created_at: datetime


class DocumentDetailRead(BaseModel):
    """Detailed document view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    organization: str | None = None
    report_year: int | None = None
    document_type: str
    status: str
    page_count: int | None = 0
    chunk_count: int | None = 0


class DocumentChunkRead(BaseModel):
    """Chunk response for search, citations, and evidence viewer (Phase 15)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_version_id: uuid.UUID
    document_id: uuid.UUID | None = None
    document_title: str | None = None
    file_name: str | None = None
    chunk_index: int
    chunk_type: str | None = None
    text: str
    page_start: int | None = None
    page_end: int | None = None
    heading_path: str | None = None
    table_html: str | None = None


class DocumentSectionRead(BaseModel):
    """Section tree node for document inspection (Phase 15)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parent_section_id: uuid.UUID | None = None
    heading: str | None = None
    heading_level: int | None = None
    section_order: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    path: str | None = None
