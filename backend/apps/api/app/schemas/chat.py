"""Pydantic schemas for /api/v1/chat and /api/v1/chat/stream endpoints.

Matches BACKEND SCHEMA.md Sections 8 & 9.
Rule 6: Exposes only message_id, answer, grounded, abstained, citations.
Rule 11: CoT reasoning is strictly excluded.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ChatCitationItem(BaseModel):
    chunk_id: str
    document_id: str | None = None
    citation_label: str | None = None
    page: int | None = None
    evidence_text: str | None = None


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = Field(
        None, description="Existing conversation ID, or None to create a new one"
    )
    message: str = Field(..., min_length=1, max_length=2000, description="User question or prompt")
    filters: dict[str, Any] | None = Field(
        None, description="Optional metadata constraints (company, year, etc.)"
    )


class ChatResponse(BaseModel):
    message_id: str
    conversation_id: str
    answer: str
    grounded: bool
    abstained: bool
    citations: list[ChatCitationItem] = Field(default_factory=list)
