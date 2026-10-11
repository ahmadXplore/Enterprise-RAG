"""Document management and access routes.

Matches BACKEND SCHEMA.md Section 5.
Rule 4: RBAC enforced on every route.
Rule 6: Data minimization and pagination.
Rule 24: Business logic delegates to DocumentService and IngestionService.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apps.api.app.api.deps import (
    check_document_access,
    get_client_ip,
    get_current_user,
    get_session,
    require_admin,
    require_viewer,
)
from apps.api.app.config import get_settings
from apps.api.app.core.audit import record_audit_log
from apps.api.app.core.rate_limit import rate_limit_ingest, rate_limit_write
from apps.api.app.models.document import Document, DocumentAccess, DocumentVersion
from apps.api.app.models.user import Role, User
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.schemas.document import (
    DocumentChunkRead,
    DocumentCreate,
    DocumentDetailRead,
    DocumentRead,
    DocumentSectionRead,
)
from apps.api.app.schemas.pagination import PaginatedResponse
from apps.api.app.services.document_service import DocumentService
from apps.api.app.services.ingestion_service import IngestionService
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.extractor import extract_educational_metadata
from packages.ingestion.normalizer import DocumentNormalizer
from packages.ingestion.parsers.dispatcher import ParserDispatcher
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.qdrant_client import create_qdrant_client
from packages.schemas.common import AccessPermission, RoleType

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[DocumentRead],
    status_code=status.HTTP_200_OK,
    summary="List documents with pagination and metadata filters",
)
async def list_documents(
    company: str | None = Query(None, description="Filter by company/organization name"),
    year: int | None = Query(None, description="Filter by report year"),
    document_type: str | None = Query(None, description="Filter by document type"),
    doc_status: str | None = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[DocumentRead]:
    """List documents accessible to the authenticated user.

    Rule 4 & 6: Non-admin users only see documents they are authorized to access.
    """
    is_admin = any(
        r.name == RoleType.ADMIN.value or r.name == RoleType.ADMIN for r in current_user.roles
    )
    allowed_ids: list[uuid.UUID] | None = None
    if not is_admin:
        doc_repo = DocumentRepository(session)
        role_ids = [r.id for r in current_user.roles]
        allowed_ids = await doc_repo.get_allowed_document_ids(
            user_id=current_user.id,
            role_ids=role_ids,
            is_admin=False,
        )

    service = DocumentService(session)
    return await service.list_documents(
        allowed_document_ids=allowed_ids,
        company=company,
        year=year,
        document_type=document_type,
        status=doc_status,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new document (Admin only)",
)
async def create_document(
    doc_in: DocumentCreate,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_write),
) -> DocumentRead:
    """Register a new document."""
    service = DocumentService(session)
    created = await service.create_document(doc_in)

    await record_audit_log(
        session=session,
        action="document:create",
        resource_type="document",
        user_id=admin_user.id,
        resource_id=created.id,
        client_ip=get_client_ip(request),
        metadata={"title": created.title},
    )
    await session.commit()
    return created


@router.post(
    "/upload",
    response_model=dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    summary="Upload and immediately process a document (Admin only)",
)
async def upload_and_process_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    organization: str | None = Form(None),
    document_type: str | None = Form(None),
    report_year: int | None = Form(None),
    request: Request = None,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_write),
) -> dict[str, Any]:
    """Upload a file, parse structure, chunk, vector-index into Qdrant, and mark ready immediately."""
    allowed_exts = {".pdf", ".docx", ".csv", ".xlsx", ".txt"}
    raw_filename = file.filename or "uploaded_document"
    safe_name = Path(raw_filename).name
    ext = Path(safe_name).suffix.lower()

    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
        )

    uploads_dir = Path("data/uploads").resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target_path = uploads_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds 50MB limit.",
        )

    file_hash = hashlib.sha256(content).hexdigest()

    doc_repo = DocumentRepository(session)
    existing_doc = await doc_repo.get_by_hash(file_hash)
    if existing_doc:
        return {
            "status": "already_exists",
            "document_id": str(existing_doc.id),
            "title": existing_doc.title,
            "organization": existing_doc.organization,
            "document_type": existing_doc.document_type,
            "filename": safe_name,
            "chunks_count": 0,
            "message": f"Document '{existing_doc.title}' has already been processed and is ready.",
        }

    with open(target_path, "wb") as f:
        f.write(content)

    meta = extract_educational_metadata(
        file_path=target_path,
        custom_title=title,
        custom_org=organization,
        custom_doc_type=document_type,
    )
    if report_year is not None:
        meta.report_year = report_year

    doc_id = uuid.uuid4()
    version_id = uuid.uuid4()

    doc = Document(
        id=doc_id,
        title=meta.title,
        source_type=meta.source_type,
        document_type=meta.document_type,
        organization=meta.organization,
        ticker=meta.ticker,
        report_year=meta.report_year,
        source_uri=str(target_path),
        content_hash=file_hash,
        language="en",
        status="processing",
    )
    session.add(doc)

    version = DocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_label="v1.0",
        source_file_path=str(target_path),
        file_name=safe_name,
        mime_type=meta.mime_type,
        file_size=len(content),
        checksum=file_hash,
        parse_status="processing",
    )
    session.add(version)

    roles_res = await session.execute(select(Role))
    roles = roles_res.scalars().all()
    for role in roles:
        session.add(
            DocumentAccess(
                id=uuid.uuid4(),
                document_id=doc_id,
                role_id=role.id,
                permission="read",
                created_at=datetime.now(UTC),
            )
        )
    await session.flush()

    try:
        dispatcher = ParserDispatcher()
        normalizer = DocumentNormalizer(target_tokens=500, overlap_tokens=60)
        parsed_doc = dispatcher.dispatch(
            file_path=target_path,
            document_id=str(doc_id),
            document_version_id=str(version_id),
        )

        sections, chunks = normalizer.normalize(parsed_doc, version_id)
        if not chunks:
            doc.status = "error"
            version.parse_status = "empty"
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to extract text or tabular chunks from the document.",
            )

        chunk_store = ChunkStore(session)
        await chunk_store.store(
            document_version_id=version_id,
            section_dicts=sections,
            chunks=chunks,
        )

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
        doc_meta = {
            "document_id": str(doc_id),
            "company": meta.organization,
            "year": meta.report_year,
            "document_type": meta.document_type,
        }
        indexed_count = indexer.index_chunks(
            chunks=chunks,
            document_metadata=doc_meta,
            batch_size=64,
        )

        doc.status = "ready"
        version.parse_status = "completed"

        await record_audit_log(
            session=session,
            action="document:upload_ingest",
            resource_type="document",
            user_id=admin_user.id,
            resource_id=doc_id,
            client_ip=get_client_ip(request),
            metadata={
                "title": doc.title,
                "filename": safe_name,
                "chunks_indexed": indexed_count,
                "sections_extracted": len(sections),
            },
        )
        await session.commit()

        return {
            "status": "ready",
            "document_id": str(doc_id),
            "version_id": str(version_id),
            "title": doc.title,
            "organization": doc.organization,
            "document_type": doc.document_type,
            "report_year": doc.report_year,
            "filename": safe_name,
            "file_size": len(content),
            "sections_count": len(sections),
            "chunks_count": indexed_count,
            "message": "Document uploaded, parsed, chunked, and vector-indexed successfully. Ready for RAG retrieval.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion processing failed: {exc}",
        ) from exc


@router.get(
    "/{document_id}",
    response_model=DocumentDetailRead,
    status_code=status.HTTP_200_OK,
    summary="Get document details with access control verification",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentDetailRead:
    """Retrieve document metadata with backend access control check."""
    await check_document_access(
        document_id=document_id,
        required_permission=AccessPermission.READ,
        current_user=current_user,
        session=session,
    )
    service = DocumentService(session)
    return await service.get_document_detail(document_id)


@router.get(
    "/{document_id}/sections",
    response_model=list[DocumentSectionRead],
    status_code=status.HTTP_200_OK,
    summary="Get document sections hierarchy (authenticated, RBAC-checked)",
)
async def get_document_sections(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentSectionRead]:
    """Retrieve section tree for document inspection (Phase 15)."""
    await check_document_access(
        document_id=document_id,
        required_permission=AccessPermission.READ,
        current_user=current_user,
        session=session,
    )
    service = DocumentService(session)
    return await service.get_sections(document_id)


@router.get(
    "/{document_id}/chunks",
    response_model=list[DocumentChunkRead],
    status_code=status.HTTP_200_OK,
    summary="Get document chunks (authenticated, RBAC-checked)",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentChunkRead]:
    """Retrieve chunks for document inspection (Phase 15)."""
    await check_document_access(
        document_id=document_id,
        required_permission=AccessPermission.READ,
        current_user=current_user,
        session=session,
    )
    service = DocumentService(session)
    return await service.get_chunks(document_id, limit=limit, offset=offset)


@router.get(
    "/chunks/{chunk_id}",
    response_model=DocumentChunkRead,
    status_code=status.HTTP_200_OK,
    summary="Get chunk details with access control verification",
)
async def get_chunk_detail(
    chunk_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentChunkRead:
    """Retrieve chunk details for evidence viewer with access check (Phase 15)."""
    service = DocumentService(session)
    chunk = await service.get_chunk_detail(chunk_id)
    from apps.api.app.models.document import DocumentVersion

    v_query = select(DocumentVersion.document_id).where(
        DocumentVersion.id == chunk.document_version_id
    )
    v_res = await session.execute(v_query)
    doc_id = v_res.scalar_one_or_none()
    if doc_id:
        await check_document_access(
            document_id=doc_id,
            required_permission=AccessPermission.READ,
            current_user=current_user,
            session=session,
        )
    return chunk


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a document (Admin only)",
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Delete a document."""
    service = DocumentService(session)
    res = await service.delete_document(document_id)

    await record_audit_log(
        session=session,
        action="document:delete",
        resource_type="document",
        user_id=admin_user.id,
        resource_id=document_id,
        client_ip=get_client_ip(request),
        metadata={},
    )
    await session.commit()
    return res


@router.post(
    "/{document_id}/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue ingestion job for a document (Admin only)",
)
async def ingest_document(
    document_id: uuid.UUID,
    _admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_ingest),
) -> dict[str, Any]:
    """Trigger ingestion job for a registered document.

    Matches BACKEND SCHEMA.md Section 6: POST /documents/{document_id}/ingest
    """
    service = IngestionService(session)
    result = await service.create_ingestion_job(document_id=document_id)
    await session.commit()
    return result
