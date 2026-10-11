"""DocumentNormalizer — converts NormalizedDocument to ORM-ready section + chunk rows.

Pure transformation: no database I/O here.
Returns (DocumentSection list, ChunkRecord list) for bulk insertion by ChunkStore.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from packages.ingestion.chunker import ChunkRecord, SemanticChunker
from packages.ingestion.parsed_document import NormalizedDocument


def _build_sections(
    doc: NormalizedDocument,
    document_version_id: uuid.UUID,
) -> list[dict]:
    """Build DocumentSection dicts from headings (heading hierarchy preserved).

    Returns a list of dicts ready to construct DocumentSection ORM objects.
    Each dict has: id, document_version_id, parent_section_id, heading,
    heading_level, section_order, page_start, page_end, path, created_at.
    """
    sections: list[dict] = []
    # Stack of (level, section_id) to resolve parent relationships
    stack: list[tuple[int, uuid.UUID]] = []

    for order, h in enumerate(doc.headings):
        # Pop entries deeper than or equal to current level
        while stack and stack[-1][0] >= h.level:
            stack.pop()

        parent_id = stack[-1][1] if stack else None
        section_id = uuid.uuid4()

        sections.append(
            {
                "id": section_id,
                "document_version_id": document_version_id,
                "parent_section_id": parent_id,
                "heading": h.text,
                "heading_level": h.level,
                "section_order": order,
                "page_start": h.page,
                "page_end": h.page,
                "path": h.path,
                "created_at": datetime.now(UTC),
            }
        )
        stack.append((h.level, section_id))

    return sections


class DocumentNormalizer:
    """Convert a NormalizedDocument into section dicts and ChunkRecord list."""

    def __init__(
        self,
        target_tokens: int = 600,
        overlap_tokens: int = 75,
        token_model: str = "cl100k_base",  # noqa: S107
    ) -> None:
        self._chunker = SemanticChunker(
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
            token_model=token_model,
        )

    def normalize(
        self,
        doc: NormalizedDocument,
        document_version_id: uuid.UUID,
    ) -> tuple[list[dict], list[ChunkRecord]]:
        """Return (section_dicts, chunk_records) for the given document.

        Args:
            doc: Parsed and normalized document.
            document_version_id: UUID of the DocumentVersion row (must exist in DB).

        Returns:
            Tuple of (section dicts, ChunkRecord list).
        """
        sections = _build_sections(doc, document_version_id)
        chunks = self._chunker.chunk(doc)
        return sections, chunks
