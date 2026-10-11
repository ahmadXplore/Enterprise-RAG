"""Document management service.

Rule 6: Minimum data exposure, explicit pagination, backend access control.
Rule 24: Business logic resides here, not in route functions.
"""

from __future__ import annotations

import math
import uuid

from apps.api.app.core.exceptions import ConflictException, NotFoundException
from apps.api.app.models.document import Document, DocumentVersion
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.schemas.document import DocumentCreate, DocumentDetailRead, DocumentRead
from apps.api.app.schemas.pagination import PaginatedResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class DocumentService:
    """Encapsulates document retrieval, filtering, creation, and deletion."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DocumentRepository(session)

    async def list_documents(
        self,
        allowed_document_ids: list[uuid.UUID] | None = None,
        company: str | None = None,
        year: int | None = None,
        document_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse[DocumentRead]:
        """Fetch paginated documents filtered by user access scope and criteria."""
        query = select(Document)

        # Pre-retrieval access scope filter (Rule 12, Rule 6)
        if allowed_document_ids is not None:
            if not allowed_document_ids:
                return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, pages=0)
            query = query.where(Document.id.in_(allowed_document_ids))

        if company:
            query = query.where(Document.organization.ilike(f"%{company}%"))
        if year:
            query = query.where(Document.report_year == year)
        if document_type:
            query = query.where(Document.document_type == document_type)
        if status:
            query = query.where(Document.status == status)

        # Count total matching
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one() or 0

        # Paginate
        offset = (page - 1) * page_size
        paginated_query = query.order_by(Document.created_at.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(paginated_query)
        docs = result.scalars().all()

        items = [DocumentRead.model_validate(d) for d in docs]
        pages = math.ceil(total / page_size) if page_size > 0 else 0

        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_document_detail(self, document_id: uuid.UUID) -> DocumentDetailRead:
        """Fetch document detail with aggregated page and chunk count."""
        query = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.versions).selectinload(DocumentVersion.chunks))
        )
        result = await self.session.execute(query)
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundException(f"Document {document_id} not found")

        total_pages = sum(v.page_count or 0 for v in doc.versions)
        total_chunks = sum(len(v.chunks) for v in doc.versions)

        return DocumentDetailRead(
            id=doc.id,
            title=doc.title,
            organization=doc.organization,
            report_year=doc.report_year,
            document_type=doc.document_type,
            status=doc.status,
            page_count=total_pages,
            chunk_count=total_chunks,
        )

    async def create_document(self, doc_in: DocumentCreate) -> DocumentRead:
        """Register a new document."""
        existing = await self.repo.get_by_hash(doc_in.content_hash)
        if existing is not None:
            raise ConflictException("A document with this content hash has already been registered")

        new_doc = Document(
            id=uuid.uuid4(),
            title=doc_in.title,
            source_type=doc_in.source_type,
            document_type=doc_in.document_type,
            organization=doc_in.organization,
            ticker=doc_in.ticker,
            report_year=doc_in.report_year,
            source_uri=doc_in.source_uri,
            content_hash=doc_in.content_hash,
            language=doc_in.language or "en",
            status="registered",
        )
        created_doc = await self.repo.create(new_doc)
        return DocumentRead.model_validate(created_doc)

    async def delete_document(self, document_id: uuid.UUID) -> dict[str, str]:
        """Delete document."""
        doc = await self.repo.get_by_id(document_id)
        if doc is None:
            raise NotFoundException(f"Document {document_id} not found")
        await self.repo.delete(doc)
        return {"message": "Document deleted successfully"}

    async def get_sections(self, document_id: uuid.UUID):
        """Fetch all section hierarchy nodes for a document."""
        from apps.api.app.schemas.document import DocumentSectionRead

        sections = await self.repo.get_sections_for_document(document_id)
        return [DocumentSectionRead.model_validate(s) for s in sections]

    async def get_chunks(self, document_id: uuid.UUID, limit: int = 100, offset: int = 0):
        """Fetch chunks for a document."""
        from apps.api.app.schemas.document import DocumentChunkRead

        chunks = await self.repo.get_chunks_for_document(document_id, limit=limit, offset=offset)
        return [DocumentChunkRead.model_validate(c) for c in chunks]

    async def get_chunk_detail(self, chunk_id: uuid.UUID):
        """Fetch single chunk details."""
        from apps.api.app.schemas.document import DocumentChunkRead

        chunk = await self.repo.get_chunk_by_id(chunk_id)
        if chunk is None:
            raise NotFoundException(f"Chunk {chunk_id} not found")
        return DocumentChunkRead.model_validate(chunk)
