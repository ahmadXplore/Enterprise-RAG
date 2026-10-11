"""ChunkStore — persists DocumentSection and DocumentChunk rows from a parse run.

Responsibilities:
- Bulk-insert DocumentSection rows.
- Bulk-insert DocumentChunk rows (upsert on re-parse by chunk_index).
- Update DocumentVersion.parse_status and Document.status on success.
- Use only parameterized ORM queries — no raw SQL.
"""
from __future__ import annotations

import logging
import uuid

from apps.api.app.models.document import Document, DocumentChunk, DocumentSection, DocumentVersion
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ingestion.chunker import ChunkRecord

logger = logging.getLogger(__name__)


class ChunkStore:
    """Bulk-persist sections and chunks for one document version."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def store(
        self,
        document_version_id: uuid.UUID,
        section_dicts: list[dict],
        chunks: list[ChunkRecord],
    ) -> None:
        """Persist all sections and chunks, then mark the version as 'chunked'.

        Args:
            document_version_id: Must reference an existing DocumentVersion row.
            section_dicts: From DocumentNormalizer.normalize() — one dict per heading.
            chunks: From SemanticChunker.chunk() — one ChunkRecord per chunk.

        Raises:
            ValueError: If document_version_id does not exist.
        """
        version = await self._get_version(document_version_id)
        if version is None:
            raise ValueError(f"DocumentVersion {document_version_id} not found")

        await self._session.execute(
            delete(DocumentSection).where(DocumentSection.document_version_id == document_version_id)
        )
        await self._insert_sections(section_dicts)
        await self._upsert_chunks(document_version_id, chunks)
        await self._mark_chunked(version)
        await self._session.flush()

        logger.info(
            "Stored %d sections, %d chunks for DocumentVersion %s",
            len(section_dicts),
            len(chunks),
            document_version_id,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_version(self, version_id: uuid.UUID) -> DocumentVersion | None:
        result = await self._session.execute(
            select(DocumentVersion).where(DocumentVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def _insert_sections(self, section_dicts: list[dict]) -> dict[uuid.UUID, uuid.UUID]:
        """Insert section rows; returns {section_id: section_id} identity map."""
        for s in section_dicts:
            section = DocumentSection(
                id=s["id"],
                document_version_id=s["document_version_id"],
                parent_section_id=s.get("parent_section_id"),
                heading=s.get("heading"),
                heading_level=s.get("heading_level"),
                section_order=s.get("section_order"),
                page_start=s.get("page_start"),
                page_end=s.get("page_end"),
                path=s.get("path"),
                metadata_=None,
            )
            self._session.add(section)
        if section_dicts:
            await self._session.flush()
        return {}

    async def _upsert_chunks(
        self, document_version_id: uuid.UUID, chunks: list[ChunkRecord]
    ) -> None:
        """Insert chunks; on conflict (version_id, chunk_index) update in place.

        The conflict target mirrors the unique constraint defined on DocumentChunk:
            (document_version_id, chunk_index)
        """
        for chunk in chunks:
            chunk_uuid = uuid.UUID(chunk.chunk_id)
            metadata = {
                "content_hash": chunk.content_hash,
            }

            # Try to find an existing chunk with the same version + index
            result = await self._session.execute(
                select(DocumentChunk).where(
                    DocumentChunk.document_version_id == document_version_id,
                    DocumentChunk.chunk_index == chunk.chunk_index,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is not None:
                # Update in place (re-parse scenario)
                existing.text = chunk.text
                existing.chunk_type = chunk.chunk_type
                existing.token_count = chunk.token_count
                existing.page_start = chunk.page_start
                existing.page_end = chunk.page_end
                existing.heading_path = chunk.section_path
                existing.table_html = chunk.table_html
                existing.content_hash = chunk.content_hash
                existing.metadata_ = metadata
            else:
                db_chunk = DocumentChunk(
                    id=chunk_uuid,
                    document_version_id=document_version_id,
                    section_id=None,  # section linking is resolved in a separate pass
                    chunk_index=chunk.chunk_index,
                    chunk_type=chunk.chunk_type,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    heading_path=chunk.section_path,
                    table_html=chunk.table_html,
                    content_hash=chunk.content_hash,
                    metadata_=metadata,
                )
                self._session.add(db_chunk)

        if chunks:
            await self._session.flush()

    async def _mark_chunked(self, version: DocumentVersion) -> None:
        """Update parse_status on the version and document status."""
        version.parse_status = "chunked"
        version.parser_name = version.parser_name or "unknown"

        # Update parent document status
        await self._session.execute(
            update(Document)
            .where(Document.id == version.document_id)
            .values(status="chunked")
        )
