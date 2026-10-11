"""Pydantic schemas for Audit Logging."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    user_id: uuid.UUID | None = None
    action: str = Field(..., max_length=100)
    resource_type: str = Field(..., max_length=50)
    resource_id: uuid.UUID | None = None
    ip_hash: str | None = Field(None, max_length=64)
    metadata: dict | None = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    created_at: datetime
