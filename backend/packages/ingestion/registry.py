"""Document registration pipeline inserting valid documents into PostgreSQL."""
import uuid
from pathlib import Path

from apps.api.app.core.audit import record_audit_log
from apps.api.app.models.document import Document, DocumentVersion
from apps.api.app.repositories.document_repo import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.validation import FileValidationResult, ValidationStatus


class DocumentRegistrar:
    """Handles atomic registration of validated files into documents & document_versions tables."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)

    async def register_document(
        self,
        validation_result: FileValidationResult,
        admin_user_id: uuid.UUID | None = None,
        client_ip: str | None = None,
    ) -> tuple[Document, DocumentVersion]:
        """Register a single validated document and its initial version."""
        if validation_result.status != ValidationStatus.VALID or not validation_result.metadata:
            raise ValueError(f"Cannot register invalid file: {validation_result.error_message}")

        if not validation_result.content_hash:
            raise ValueError("Cannot register document without SHA-256 content hash")

        meta = validation_result.metadata
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
            source_uri=meta.source_uri,
            content_hash=validation_result.content_hash,
            language="en",
            status="registered",
        )
        await self.doc_repo.create(doc)

        version = DocumentVersion(
            id=version_id,
            document_id=doc_id,
            version_label="v1.0",
            source_file_path=validation_result.file_path,
            file_name=meta.original_filename,
            mime_type=meta.mime_type,
            file_size=meta.file_size,
            checksum=validation_result.content_hash,
            parse_status="pending",
        )
        self.session.add(version)
        await self.session.flush()

        # Audit log the registration action
        await record_audit_log(
            session=self.session,
            action="corpus:register_document",
            resource_type="document",
            user_id=admin_user_id,
            resource_id=doc_id,
            client_ip=client_ip,
            metadata={
                "title": doc.title,
                "source_type": doc.source_type,
                "content_hash": doc.content_hash,
                "file_path": Path(validation_result.file_path).name,
            },
        )

        return doc, version
