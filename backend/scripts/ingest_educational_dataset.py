"""Ingest the Educational Dataset (PDFs, DOCX, CSV, XLSX) into PostgreSQL/SQLite and Qdrant.

Scans d:/RAG/EDUCATIONAL DATA, registers documents with metadata, grants RBAC access to all roles,
parses content, chunks with semantic overlap, stores in the database, and indexes into Qdrant.

Usage:
    python backend/scripts/ingest_educational_dataset.py --limit 20
    python backend/scripts/ingest_educational_dataset.py --all
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.app.config import get_settings
from apps.api.app.core.database import AsyncSessionLocal
from apps.api.app.models.document import Document, DocumentAccess, DocumentVersion
from apps.api.app.models.user import Role
from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.extractor import extract_educational_metadata
from packages.ingestion.normalizer import DocumentNormalizer
from packages.ingestion.parsers.dispatcher import ParserDispatcher
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.qdrant_client import create_qdrant_client
from sqlalchemy import select

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_educational")


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


async def ingest_educational_corpus(limit_per_category: int | None = None, total_limit: int | None = None) -> None:
    settings = get_settings()
    logger.info("Connecting to Qdrant at %s...", settings.QDRANT_URL)
    qdrant_client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    logger.info("Initializing Dense (FastEmbed BGE) and Sparse (BM25) embedders...")
    dense_embedder = FastEmbedDenseEmbedder()
    sparse_embedder = BM25SparseEmbedder()

    indexer = QdrantIndexer(
        client=qdrant_client,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        collection_name="enterprise_rag_chunks",
    )

    dispatcher = ParserDispatcher()
    normalizer = DocumentNormalizer(target_tokens=500, overlap_tokens=60)

    base_dir = Path("EDUCATIONAL DATA").resolve()
    if not base_dir.exists():
        logger.error("EDUCATIONAL DATA directory not found at %s", base_dir)
        return

    # Gather files from subdirectories
    categories = ["pdfs", "docx", "csv", "xlsx"]
    categorized_files: dict[str, list[Path]] = {}
    for cat in categories:
        cat_dir = base_dir / cat
        if cat_dir.exists():
            files = [
                f for f in sorted(cat_dir.glob("*.*"))
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in {".pdf", ".docx", ".csv", ".xlsx"}
            ]
            if limit_per_category:
                files = files[:limit_per_category]
            categorized_files[cat] = files
        else:
            categorized_files[cat] = []

    all_files: list[Path] = []
    for cat in categories:
        all_files.extend(categorized_files[cat])

    if total_limit and len(all_files) > total_limit:
        all_files = all_files[:total_limit]

    logger.info(
        "Discovered %d educational files to ingest (PDFs: %d, DOCX: %d, CSV: %d, XLSX: %d)",
        len(all_files),
        len(categorized_files.get("pdfs", [])),
        len(categorized_files.get("docx", [])),
        len(categorized_files.get("csv", [])),
        len(categorized_files.get("xlsx", [])),
    )

    async with AsyncSessionLocal() as session:
        # Fetch existing roles so we can grant read permissions
        roles_res = await session.execute(select(Role))
        roles = list(roles_res.scalars().all())
        logger.info("Found %d roles for document access assignment: %s", len(roles), [r.name for r in roles])

        # Fetch existing document hashes to skip already ingested
        existing_hashes_res = await session.execute(select(Document.content_hash))
        existing_hashes = set(existing_hashes_res.scalars().all())
        logger.info("Found %d already registered documents in DB", len(existing_hashes))

        total_processed = 0
        total_chunks = 0
        total_errors = 0

        for idx, file_path in enumerate(all_files, start=1):
            file_hash = compute_file_hash(file_path)
            if file_hash in existing_hashes:
                logger.info("[%d/%d] Skipping already registered: %s", idx, len(all_files), file_path.name)
                continue

            logger.info("[%d/%d] Ingesting: %s (%s)", idx, len(all_files), file_path.name, file_path.suffix.upper())

            try:
                # 1. Extract metadata
                meta = extract_educational_metadata(file_path)

                # 2. Register Document & DocumentVersion
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
                    content_hash=file_hash,
                    language="en",
                    status="processing",
                )
                session.add(doc)

                version = DocumentVersion(
                    id=version_id,
                    document_id=doc_id,
                    version_label="v1.0",
                    source_file_path=str(file_path),
                    file_name=meta.original_filename,
                    mime_type=meta.mime_type,
                    file_size=meta.file_size,
                    checksum=file_hash,
                    parse_status="processing",
                )
                session.add(version)

                # 3. Grant DocumentAccess to all roles
                for role in roles:
                    acc = DocumentAccess(
                        id=uuid.uuid4(),
                        document_id=doc_id,
                        role_id=role.id,
                        permission="read",
                        created_at=datetime.now(UTC),
                    )
                    session.add(acc)

                await session.flush()

                # 4. Parse content
                parsed_doc = dispatcher.dispatch(
                    file_path=file_path,
                    document_id=str(doc_id),
                    document_version_id=str(version_id),
                )

                # 5. Normalize and Chunk
                sections, chunks = normalizer.normalize(parsed_doc, version_id)

                if not chunks:
                    logger.warning("  No chunks generated for %s, marking skipped", file_path.name)
                    doc.status = "error"
                    version.parse_status = "empty"
                    await session.commit()
                    continue

                # 6. Store sections and chunks in DB
                chunk_store = ChunkStore(session)
                await chunk_store.store(
                    document_version_id=version_id,
                    section_dicts=sections,
                    chunks=chunks,
                )

                # 7. Index in Qdrant
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

                # 8. Mark ready
                doc.status = "ready"
                version.parse_status = "completed"
                await session.commit()

                existing_hashes.add(file_hash)
                total_processed += 1
                total_chunks += indexed_count
                logger.info(
                    "  [SUCCESS] %s: %d sections, %d chunks indexed into Qdrant",
                    file_path.name[:45],
                    len(sections),
                    indexed_count,
                )

            except Exception as exc:
                logger.error("  [FAILED] Failed to ingest %s: %s", file_path.name, exc, exc_info=True)
                await session.rollback()
                total_errors += 1

        logger.info(
            "Educational Ingestion Complete! Successfully indexed %d documents (%d chunks), %d errors.",
            total_processed,
            total_chunks,
            total_errors,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Educational Dataset")
    parser.add_argument("--limit-per-cat", type=int, default=None, help="Limit files per category (pdfs, docx, csv, xlsx)")
    parser.add_argument("--total-limit", type=int, default=None, help="Total limit across all categories")
    parser.add_argument("--all", action="store_true", help="Ingest all files in EDUCATIONAL DATA")
    args = parser.parse_args()

    asyncio.run(ingest_educational_corpus(limit_per_category=args.limit_per_cat, total_limit=args.total_limit))
