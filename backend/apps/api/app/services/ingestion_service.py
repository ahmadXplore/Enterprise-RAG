"""Ingestion service managing ingestion job lifecycle.

Matches BACKEND SCHEMA.md Section 6.
Stages: validation, parsing, normalization, chunking, embedding, indexing, completed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from apps.api.app.core.exceptions import NotFoundException
from apps.api.app.models.ingestion import IngestionJob
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.repositories.job_repo import IngestionJobRepository
from sqlalchemy.ext.asyncio import AsyncSession


class IngestionService:
    """Manages ingestion jobs for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.job_repo = IngestionJobRepository(session)
        self.doc_repo = DocumentRepository(session)

    async def create_ingestion_job(
        self,
        document_id: uuid.UUID,
        job_type: str = "full_ingest",
    ) -> dict[str, Any]:
        """Enqueue an ingestion job for a registered document."""
        doc = await self.doc_repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundException(f"Document {document_id} not found")

        # Idempotency guard (Phase 17): Return existing active/queued job if already in flight
        recent_jobs = await self.job_repo.list_recent(limit=50)
        for existing in recent_jobs:
            if existing.document_id == document_id and existing.status in {"queued", "running"}:
                return {
                    "job_id": str(existing.id),
                    "status": existing.status,
                    "message": "Job already queued or running",
                }

        job = IngestionJob(
            id=uuid.uuid4(),
            document_id=document_id,
            job_type=job_type,
            status="queued",
            progress=0,
            current_stage="validation",
            started_at=datetime.now(UTC),
        )
        created = await self.job_repo.create(job)
        return {"job_id": str(created.id), "status": created.status}

    async def get_job_status(self, job_id: uuid.UUID) -> dict[str, Any]:
        """Fetch current ingestion job progress and stage."""
        job = await self.job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundException(f"Ingestion job {job_id} not found")

        return {
            "job_id": str(job.id),
            "status": job.status,
            "progress": job.progress,
            "stage": job.current_stage or "validation",
        }

    async def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch list of recent ingestion jobs."""
        jobs = await self.job_repo.list_recent(limit=limit)
        return [
            {
                "job_id": str(j.id),
                "document_id": str(j.document_id),
                "status": j.status,
                "progress": j.progress,
                "stage": j.current_stage or "validation",
                "error_message": j.error_message,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]
