"""Pydantic request and response schemas for the /api/v1/query endpoint.

Rule 6: Response schema exposes only the minimum data required by the client.
Rule 11: Chain-of-thought internal state is never present in these schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request body for POST /api/v1/query."""

    question: str = Field(..., min_length=1, max_length=2000)
    # Optional metadata filters — sanitised on the backend, never used for auth
    company: str | None = Field(None, max_length=255)
    year: int | None = Field(None, ge=1900, le=2100)
    document_type: str | None = Field(None, max_length=100)


class CitationRead(BaseModel):
    """A single citation in a grounded answer."""

    chunk_id: str
    # Consumers may use chunk_id to look up the original chunk via the documents API


class QueryResponse(BaseModel):
    """Response schema for POST /api/v1/query.

    Rule 6: Only fields needed by the client.  CoT / internal state is excluded.
    """

    answer: str
    citation_ids: list[str]
    grounded: bool
    abstained: bool
    query_type: str
    # token_usage intentionally omitted from the client response (Rule 6)
