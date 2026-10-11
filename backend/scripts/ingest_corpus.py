"""Script to parse, chunk, store, and index registered documents into the database and Qdrant.

Usage:
    python backend/scripts/ingest_corpus.py --limit 10
    python backend/scripts/ingest_corpus.py --company Apple
    python backend/scripts/ingest_corpus.py --all
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import uuid
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.api.app.config import get_settings
from apps.api.app.core.database import AsyncSessionLocal
from apps.api.app.models.document import Document, DocumentVersion
from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.normalizer import DocumentNormalizer
from packages.ingestion.parsers.dispatcher import ParserDispatcher
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.indexer import QdrantIndexer
from packages.retrieval.qdrant_client import create_qdrant_client
from sqlalchemy import select, update

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_corpus")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest and Index Registered Documents")
    parser.add_argument("--limit", type=int, default=None, help="Max documents to ingest")
    parser.add_argument("--organization", "--company", dest="company", type=str, default=None, help="Filter by organization or institution name")
    parser.add_argument("--doc-type", type=str, default=None, help="Filter by document type")
    parser.add_argument("--reindex", action="store_true", help="Force reindexing even if already in Qdrant")
    parser.add_argument("--all", action="store_true", help="Ingest all registered documents")
    args = parser.parse_args()

    settings = get_settings()
    logger.info("Initializing Qdrant client at %s...", settings.QDRANT_URL)
    qdrant_client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    indexed_doc_ids = set()
    if not args.reindex:
        try:
            offset = None
            while True:
                points, offset = qdrant_client.scroll(
                    collection_name="enterprise_rag_chunks",
                    limit=1000,
                    offset=offset,
                    with_payload=["document_id"],
                    with_vectors=False,
                )
                for p in points:
                    if p.payload and "document_id" in p.payload:
                        indexed_doc_ids.add(p.payload["document_id"])
                if offset is None:
                    break
            logger.info("Found %d documents already indexed in Qdrant.", len(indexed_doc_ids))
        except Exception as e:
            logger.warning("Could not check existing Qdrant points: %s", e)

    logger.info("Loading dense (FastEmbed BGE) and sparse (BM25) embedders...")
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

    async with AsyncSessionLocal() as session:
        # Fetch documents and their primary versions
        query = (
            select(Document, DocumentVersion)
            .join(DocumentVersion, Document.id == DocumentVersion.document_id)
            .order_by(Document.report_year.desc().nullslast(), Document.title)
        )

        if args.company:
            query = query.where(Document.organization.ilike(f"%{args.company}%"))

        if args.doc_type:
            query = query.where(Document.document_type == args.doc_type)

        result = await session.execute(query)
        rows = result.all()

        if not rows:
            logger.warning("No documents matched criteria.")
            return

        # Filter out already indexed if not reindexing
        if not args.reindex and indexed_doc_ids:
            unindexed_rows = [(doc, ver) for doc, ver in rows if str(doc.id) not in indexed_doc_ids]
            logger.info(
                "Total matching: %d | Already indexed: %d | Remaining to index: %d",
                len(rows),
                len(rows) - len(unindexed_rows),
                len(unindexed_rows),
            )
            rows = unindexed_rows
        else:
            logger.info("Found %d documents to process.", len(rows))

        if args.limit:
            rows = rows[: args.limit]

        total_chunks_indexed = 0
        total_docs_processed = 0

        for doc, version in rows:
            file_path = Path(version.source_file_path)
            if not file_path.exists():
                logger.warning("File not found: %s (Doc ID: %s), skipping", file_path, doc.id)
                continue

            logger.info("Processing: %s [%s - %s]", doc.title, doc.organization, doc.report_year)

            try:
                # 1. Parse document
                parsed_doc = dispatcher.dispatch(
                    file_path=file_path,
                    document_id=str(doc.id),
                    document_version_id=str(version.id),
                )

                # 2. Normalize and Chunk
                sections, chunks = normalizer.normalize(parsed_doc, version.id)
                logger.info(
                    "  Generated %d sections and %d chunks",
                    len(sections),
                    len(chunks),
                )

                if not chunks:
                    logger.warning("  No chunks generated for %s", doc.title)
                    continue

                # 3. Store sections and chunks in DB
                chunk_store = ChunkStore(session)
                await chunk_store.store(
                    document_version_id=version.id,
                    section_dicts=sections,
                    chunks=chunks,
                )

                # 4. Index in Qdrant
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

                # 5. Update document status to ready only after indexing succeeds
                await session.execute(
                    update(Document).where(Document.id == doc.id).values(status="ready")
                )
                await session.commit()

                total_chunks_indexed += indexed_count
                total_docs_processed += 1
                logger.info(
                    "  Indexed %d points into Qdrant for %s",
                    indexed_count,
                    doc.title,
                )

            except Exception as exc:
                logger.error("Failed to ingest %s: %s", doc.title, exc, exc_info=True)
                await session.rollback()

        logger.info(
            "Ingestion completed! Processed %d documents, indexed %d total chunks into Qdrant.",
            total_docs_processed,
            total_chunks_indexed,
        )


if __name__ == "__main__":
    asyncio.run(main())
