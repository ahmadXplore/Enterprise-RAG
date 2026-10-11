"""Pydantic schemas for Ingestion Job operations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngestionJobCreate(BaseModel):
    document_id: uuid.UUID
    document_version_id: uuid.UUID | None = None
    job_type: str = Field("full_ingest", description="Job type: parse, embed, index, full_ingest")


class IngestionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    job_type: str
    status: str
    progress: int
    current_stage: str | None = None
    error_message: str | None = None
    created_at: datetime
