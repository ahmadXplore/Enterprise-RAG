"""Pydantic schemas for Document Access Control."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentAccessCreate(BaseModel):
    document_id: uuid.UUID
    user_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    permission: str = Field("read", description="Permission level: read, manage, admin")


class DocumentAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    permission: str
    created_at: datetime
