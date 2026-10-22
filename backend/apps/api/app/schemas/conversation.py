"""Pydantic schemas for Conversation and Message management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(None, max_length=255)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class MessageCitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_id: uuid.UUID | None = None
    citation_label: str | None = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    query_type: str | None = None
    grounded: bool | None = None
    abstained: bool = False
    created_at: datetime
    citations: list[MessageCitationRead] = []


class ConversationDetailRead(ConversationRead):
    messages: list[MessageRead] = []

