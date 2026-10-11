"""Document and Chunk repository with Pre-Retrieval Authorization resolution."""
import uuid
from collections.abc import Sequence

from apps.api.app.models.document import (
    Document,
    DocumentAccess,
    DocumentChunk,
    DocumentSection,
    DocumentVersion,
)
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class DocumentRepository(BaseRepository[Document]):
    def __init__(self, session: AsyncSession):
        super().__init__(Document, session)

    async def get_by_hash(self, content_hash: str) -> Document | None:
        """Fetch document by unique SHA-256 hash to prevent duplicate ingestion."""
        query = select(Document).where(Document.content_hash == content_hash)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_versions(self, document_id: uuid.UUID) -> Document | None:
        """Fetch document with versions."""
        query = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_allowed_document_ids(
        self,
        user_id: uuid.UUID,
        role_ids: list[uuid.UUID],
        is_admin: bool = False,
    ) -> list[uuid.UUID]:
        """Resolve exact allowed document IDs for pre-retrieval access control.

        Architectural Requirement (TRD Section 16.1 & 25):
        The LLM should never decide document authorization.
        This resolution happens strictly at the database layer before vector retrieval.
        """
        if is_admin:
            # Admins have access to all registered documents
            query = select(Document.id)
            result = await self.session.execute(query)
            return list(result.scalars().all())

        # Resolve explicit user access or role-based access
        access_conditions = [DocumentAccess.user_id == user_id]
        if role_ids:
            access_conditions.append(DocumentAccess.role_id.in_(role_ids))

        query = (
            select(DocumentAccess.document_id)
            .where(or_(*access_conditions))
            .distinct()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_chunks_for_version(
        self, document_version_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[DocumentChunk]:
        """Fetch chunks for a specific document version."""
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_version_id == document_version_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_sections_for_document(self, document_id: uuid.UUID) -> Sequence[DocumentSection]:
        """Fetch all sections across versions for a document."""
        from apps.api.app.models.document import DocumentSection

        query = (
            select(DocumentSection)
            .join(DocumentVersion, DocumentSection.document_version_id == DocumentVersion.id)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentSection.section_order)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_chunks_for_document(
        self, document_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[DocumentChunk]:
        """Fetch all chunks for a document across its versions."""
        from apps.api.app.models.document import DocumentChunk

        query = (
            select(DocumentChunk)
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_chunk_by_id(self, chunk_id: uuid.UUID) -> DocumentChunk | None:
        """Fetch a single chunk by its ID."""
        query = select(DocumentChunk).where(DocumentChunk.id == chunk_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
