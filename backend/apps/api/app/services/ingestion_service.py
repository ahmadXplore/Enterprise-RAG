"""Ingestion service managing ingestion job lifecycle.

Matches BACKEND SCHEMA.md Section 6.
Stages: validation, parsing, normalization, chunking, embedding, indexing, completed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.api.app.config import get_settings
from apps.api.app.core.database import AsyncSessionLocal
from apps.api.app.core.exceptions import NotFoundException
from apps.api.app.core.logging import logger
from apps.api.app.models.document import Document, DocumentVersion
from apps.api.app.models.ingestion import IngestionJob
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.repositories.job_repo import IngestionJobRepository
from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.normalizer import DocumentNormalizer
from packages.ingestion.parsers.dispatcher import ParserDispatcher
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.qdrant_client import create_qdrant_client
from sqlalchemy import select
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
        document_version_id: uuid.UUID | None = None,
        job_type: str = "full_ingest",
    ) -> dict[str, Any]:
        """Enqueue an ingestion job for a registered document."""
        doc = await self.doc_repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundException(f"Document {document_id} not found")

        # Idempotency guard: Return existing active/queued job if already in flight
        recent_jobs = await self.job_repo.list_recent(limit=50)
        for existing in recent_jobs:
            if existing.document_id == document_id and existing.status in {"queued", "processing", "running"}:
                return {
                    "job_id": str(existing.id),
                    "status": existing.status,
                    "message": "Job already queued or running",
                }

        job = IngestionJob(
            id=uuid.uuid4(),
            document_id=document_id,
            document_version_id=document_version_id,
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
            "error_message": job.error_message,
        }

    async def list_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch list of recent ingestion jobs with document title."""
        query = (
            select(IngestionJob, Document.title)
            .outerjoin(Document, IngestionJob.document_id == Document.id)
            .order_by(IngestionJob.created_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(query)
        rows = res.all()
        return [
            {
                "job_id": str(j.id),
                "document_id": str(j.document_id),
                "document_title": title or "Untitled Document",
                "status": j.status,
                "progress": j.progress,
                "stage": j.current_stage or "validation",
                "error_message": j.error_message,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j, title in rows
        ]


async def process_ingestion_job(job_id: uuid.UUID) -> None:
    """Execute asynchronous multi-stage ingestion pipeline for an IngestionJob.

    Stages: validation (10%) -> parsing (25%) -> chunking (50%) -> embedding (75%) -> indexing (90%) -> completed (100%).
    """
    logger.info("Starting background ingestion pipeline for job %s", job_id)
    async with AsyncSessionLocal() as session:
        job = await session.get(IngestionJob, job_id)
        if not job:
            logger.error("Job %s not found in background pipeline", job_id)
            return

        doc = await session.get(Document, job.document_id)
        if not doc:
            job.status = "failed"
            job.error_message = f"Document {job.document_id} not found"
            job.finished_at = datetime.now(UTC)
            await session.commit()
            return

        # Find document version
        version: DocumentVersion | None = None
        if job.document_version_id:
            version = await session.get(DocumentVersion, job.document_version_id)
        if not version:
            v_query = (
                select(DocumentVersion)
                .where(DocumentVersion.document_id == doc.id)
                .order_by(DocumentVersion.created_at.desc())
            )
            v_res = await session.execute(v_query)
            version = v_res.scalars().first()

        if not version or not version.source_file_path:
            job.status = "failed"
            job.error_message = "Document version or source file path not found"
            job.finished_at = datetime.now(UTC)
            doc.status = "error"
            await session.commit()
            return

        target_path = Path(version.source_file_path)

        try:
            # Stage 1: Validation (10%)
            job.status = "processing"
            job.current_stage = "validation"
            job.progress = 10
            job.started_at = datetime.now(UTC)
            doc.status = "processing"
            version.parse_status = "processing"
            await session.commit()

            if not target_path.exists():
                raise FileNotFoundError(f"Source file '{target_path}' not found on disk")

            # Stage 2: Parsing (25%)
            job.current_stage = "parsing"
            job.progress = 25
            await session.commit()

            dispatcher = ParserDispatcher()
            parsed_doc = dispatcher.dispatch(
                file_path=target_path,
                document_id=str(doc.id),
                document_version_id=str(version.id),
            )

            # Stage 3: Normalization & Chunking (50%)
            job.current_stage = "chunking"
            job.progress = 50
            await session.commit()

            normalizer = DocumentNormalizer(target_tokens=500, overlap_tokens=60)
            sections, chunks = normalizer.normalize(parsed_doc, version.id)
            if not chunks:
                raise ValueError("Unable to extract text or tabular chunks from the document.")

            chunk_store = ChunkStore(session)
            await chunk_store.store(
                document_version_id=version.id,
                section_dicts=sections,
                chunks=chunks,
            )

            # Stage 4: Embedding (75%) & Indexing (90%)
            job.current_stage = "embedding"
            job.progress = 75
            await session.commit()

            settings = get_settings()
            qdrant_client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
            dense_embedder = FastEmbedDenseEmbedder()
            sparse_embedder = BM25SparseEmbedder()
            indexer = QdrantIndexer(
                client=qdrant_client,
                dense_embedder=dense_embedder,
                sparse_embedder=sparse_embedder,
                collection_name="enterprise_rag_chunks",
            )

            job.current_stage = "indexing"
            job.progress = 90
            await session.commit()

            doc_meta = {
                "document_id": str(doc.id),
                "company": doc.organization,
                "year": doc.report_year,
                "document_type": doc.document_type,
            }
            indexed_count = indexer.index_chunks(
                chunks=chunks,
                document_metadata=doc_meta,
                batch_size=64,
            )

            # Stage 5: Completed (100%)
            doc.status = "ready"
            version.parse_status = "completed"
            job.status = "completed"
            job.current_stage = "completed"
            job.progress = 100
            job.finished_at = datetime.now(UTC)
            await session.commit()
            logger.info("Successfully completed ingestion for job %s (indexed %d chunks)", job_id, indexed_count)

        except Exception as exc:
            logger.exception("Ingestion pipeline failed for job %s: %s", job_id, exc)
            await session.rollback()
            try:
                fail_job = await session.get(IngestionJob, job_id)
                if fail_job:
                    fail_job.status = "failed"
                    fail_job.error_message = str(exc)
                    fail_job.finished_at = datetime.now(UTC)
                fail_doc = await session.get(Document, doc.id)
                if fail_doc:
                    fail_doc.status = "error"
                if version:
                    fail_ver = await session.get(DocumentVersion, version.id)
                    if fail_ver:
                        fail_ver.parse_status = "error"
                await session.commit()
            except Exception as final_err:
                logger.error("Failed to commit failure status for job %s: %s", job_id, final_err)
