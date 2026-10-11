"""Pydantic schemas for /api/v1/search endpoint.

Matches BACKEND SCHEMA.md Section 7 exactly.
Rule 6: Exposes only search results and metadata required by the search UI.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    companies: list[str] | None = None
    years: list[int] | None = None
    document_type: str | None = None
    extra: dict[str, Any] | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="User search query")
    filters: SearchFilters | None = None
    top_k: int = Field(10, ge=1, le=50, description="Number of results to retrieve")


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    score: float
    text: str
    company: str | None = None
    year: int | None = None
    page: int | None = None
    document_title: str | None = None
    document_type: str | None = None


class SearchResponse(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    results: list[SearchResultItem]
    message: str | None = None
    available_resources: list[str] | None = None
