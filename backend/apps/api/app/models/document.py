"""Document, Version, Section, Chunk, and Access Control models."""
import uuid
from datetime import UTC, datetime

from apps.api.app.models.base import Base, TimestampMixin
from apps.api.app.models.types import GUID, CompatibleJSONB
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(20), nullable=True)
    report_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(20), default="en", nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="registered", nullable=False)

    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )
    access_controls: Mapped[list["DocumentAccess"]] = relationship(
        "DocumentAccess", back_populates="document", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(  # noqa: F821
        "IngestionJob", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_documents_org_year", "organization", "report_year"),
        Index("idx_documents_type", "document_type"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_label: Mapped[str | None] = mapped_column(String(50), default="v1.0", nullable=True)
    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parser_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parse_status: Mapped[str | None] = mapped_column(String(50), default="pending", nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped[Document] = relationship("Document", back_populates="versions")
    sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection", back_populates="document_version", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk", back_populates="document_version", cascade="all, delete-orphan"
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_section_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=True, index=True
    )
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    heading_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", CompatibleJSONB(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document_version: Mapped[DocumentVersion] = relationship(
        "DocumentVersion", back_populates="sections"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="section")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_type: Mapped[str | None] = mapped_column(String(50), default="paragraph", nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    table_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", CompatibleJSONB(), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document_version: Mapped[DocumentVersion] = relationship(
        "DocumentVersion", back_populates="chunks"
    )
    section: Mapped[DocumentSection | None] = relationship(
        "DocumentSection", back_populates="chunks"
    )

    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_version_chunk_index"),
        Index("idx_chunks_document", "document_version_id"),
        Index("idx_chunks_section", "section_id"),
    )


class DocumentAccess(Base):
    """Document access control rules (Pre-retrieval authorization per TRD Section 16.1 & 25)."""
    __tablename__ = "document_access"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    permission: Mapped[str] = mapped_column(String(50), nullable=False)  # read, manage, admin
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    document: Mapped[Document] = relationship("Document", back_populates="access_controls")
