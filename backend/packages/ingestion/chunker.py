"""SemanticChunker — converts a NormalizedDocument into retrieval-ready chunks.

Strategy (per TRD §6):
- Hierarchical, not blind fixed-size splitting.
- Paragraphs within token limit  → emitted as 'paragraph' chunks.
- Long paragraphs (> target)     → split at sentence boundary with overlap.
- Tables                         → single 'table' chunk when ≤ target tokens;
                                   split by row-group (preserving header) when larger.
- Adjacent short paragraphs      → merged up to target tokens under same heading.
- Headings alone (no children)   → emitted as 'section' chunks.

Chunk IDs are deterministic: UUID5(NAMESPACE_DNS, f"{document_version_id}:{chunk_index}").
This guarantees identical output for identical input across re-parses.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field

from packages.ingestion.parsed_document import NormalizedDocument, ParsedTable

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

try:
    import tiktoken  # type: ignore[import-untyped]

    def _count_tokens(text: str, model: str) -> int:
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

    def _count_tokens(text: str, model: str) -> int:  # type: ignore[misc]
        # Fallback approximation: 1 token ≈ 4 chars (GPT-4 average)
        return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# ChunkRecord — maps 1:1 to the document_chunks ORM model
# ---------------------------------------------------------------------------

@dataclass
class ChunkRecord:
    """One chunk ready for database insertion."""

    chunk_id: str               # deterministic UUID string
    document_version_id: str
    section_path: str           # heading_path in DB
    chunk_index: int
    chunk_type: str             # paragraph | section | table | table_row_group | list
    text: str
    table_html: str | None
    page_start: int | None
    page_end: int | None
    token_count: int
    content_hash: str           # sha256 hex of text
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# SemanticChunker
# ---------------------------------------------------------------------------

_CHUNK_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # uuid.NAMESPACE_DNS


def _deterministic_chunk_id(document_version_id: str, chunk_index: int) -> str:
    """Return a deterministic UUID string for a chunk.

    Derived from UUID5(NAMESPACE_DNS, "{version_id}:{index}") so the same
    document + same chunk index always produces the same ID.
    """
    name = f"{document_version_id}:{chunk_index}"
    return str(uuid.uuid5(_CHUNK_ID_NAMESPACE, name))


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries (. ! ? followed by space or end)."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _split_by_words(text: str, target_tokens: int, token_model: str) -> list[str]:
    """Split text purely on whitespace into token-bounded segments.

    Used as a fallback when a 'sentence' has no punctuation and exceeds
    target_tokens (e.g. repeated single words like 'Word ' * 500).
    """
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_tokens = 0
    for word in words:
        wt = _count_tokens(word, token_model)
        if buffer_tokens + wt > target_tokens and buffer:
            chunks.append(" ".join(buffer))
            buffer = []
            buffer_tokens = 0
        buffer.append(word)
        buffer_tokens += wt
    if buffer:
        chunks.append(" ".join(buffer))
    return chunks



class SemanticChunker:
    """Convert a NormalizedDocument into a list of ChunkRecord objects."""

    def __init__(
        self,
        target_tokens: int = 600,
        overlap_tokens: int = 75,
        token_model: str = "cl100k_base",  # noqa: S107
    ) -> None:
        if target_tokens < 10:
            raise ValueError("target_tokens must be >= 10")
        if overlap_tokens < 0 or overlap_tokens >= target_tokens:
            raise ValueError("overlap_tokens must be in [0, target_tokens)")
        self.target = target_tokens
        self.overlap = overlap_tokens
        self.token_model = token_model

    def chunk(self, doc: NormalizedDocument) -> list[ChunkRecord]:
        """Return deterministic, ordered chunks for *doc*."""
        chunks: list[ChunkRecord] = []
        chunk_index = 0

        # Build a list of (section_path, elements) by grouping paragraphs
        # under the heading that was active when they were extracted.
        groups = _group_by_section(doc)

        for section_path, paragraphs, tables_in_section in groups:
            # --- Tables in this section ---
            for tbl in tables_in_section:
                new_chunks, chunk_index = self._chunk_table(
                    tbl, section_path, doc.document_version_id, chunk_index
                )
                chunks.extend(new_chunks)

            # --- Paragraphs in this section ---
            new_chunks, chunk_index = self._chunk_paragraphs(
                paragraphs, section_path, doc.document_version_id, chunk_index
            )
            chunks.extend(new_chunks)

        # --- Top-level tables not assigned to any section ---
        assigned_tables = {id(t) for _, _, tbls in groups for t in tbls}
        for tbl in doc.tables:
            if id(tbl) not in assigned_tables:
                new_chunks, chunk_index = self._chunk_table(
                    tbl, tbl.section_path, doc.document_version_id, chunk_index
                )
                chunks.extend(new_chunks)

        return chunks

    # ------------------------------------------------------------------
    # Paragraph chunking
    # ------------------------------------------------------------------

    def _chunk_paragraphs(
        self,
        paragraphs: list[tuple[str, int | None]],  # (text, page)
        section_path: str,
        document_version_id: str,
        chunk_index: int,
    ) -> tuple[list[ChunkRecord], int]:
        """Merge adjacent short paragraphs; split long ones at sentence boundaries."""
        chunks: list[ChunkRecord] = []
        buffer_texts: list[str] = []
        buffer_pages: list[int] = []
        buffer_tokens = 0

        def _flush() -> None:
            nonlocal chunk_index
            if not buffer_texts:
                return
            text = "\n\n".join(buffer_texts)
            page_start = min(buffer_pages) if buffer_pages else None
            page_end = max(buffer_pages) if buffer_pages else None
            chunks.append(
                ChunkRecord(
                    chunk_id=_deterministic_chunk_id(document_version_id, chunk_index),
                    document_version_id=document_version_id,
                    section_path=section_path,
                    chunk_index=chunk_index,
                    chunk_type="paragraph",
                    text=text,
                    table_html=None,
                    page_start=page_start,
                    page_end=page_end,
                    token_count=_count_tokens(text, self.token_model),
                    content_hash=_content_hash(text),
                )
            )
            chunk_index += 1
            buffer_texts.clear()
            buffer_pages.clear()

        for text, page in paragraphs:
            tokens = _count_tokens(text, self.token_model)

            if tokens > self.target:
                # Flush pending buffer first
                _flush()
                # Split long paragraph at sentence boundaries
                split_chunks, chunk_index = self._split_long_text(
                    text, page, page, section_path, document_version_id, chunk_index
                )
                chunks.extend(split_chunks)
                continue

            if buffer_tokens + tokens > self.target and buffer_texts:
                _flush()

            buffer_texts.append(text)
            if page is not None:
                buffer_pages.append(page)
            buffer_tokens = _count_tokens("\n\n".join(buffer_texts), self.token_model)

        _flush()
        return chunks, chunk_index

    def _split_long_text(
        self,
        text: str,
        page_start: int | None,
        page_end: int | None,
        section_path: str,
        document_version_id: str,
        chunk_index: int,
    ) -> tuple[list[ChunkRecord], int]:
        """Split *text* at sentence boundaries with overlap.

        If a single 'sentence' exceeds target_tokens (e.g. no punctuation),
        it is further split by whitespace to guarantee bounded output size.
        """
        sentences = _split_sentences(text)
        # Further split any sentence that still exceeds target
        expanded: list[str] = []
        for sent in sentences:
            if _count_tokens(sent, self.token_model) > self.target:
                expanded.extend(_split_by_words(sent, self.target, self.token_model))
            else:
                expanded.append(sent)
        sentences = expanded
        chunks: list[ChunkRecord] = []
        window: list[str] = []
        window_tokens = 0

        i = 0
        while i < len(sentences):
            sent = sentences[i]
            sent_tokens = _count_tokens(sent, self.token_model)

            if window_tokens + sent_tokens > self.target and window:
                chunk_text = " ".join(window)
                chunks.append(
                    ChunkRecord(
                        chunk_id=_deterministic_chunk_id(document_version_id, chunk_index),
                        document_version_id=document_version_id,
                        section_path=section_path,
                        chunk_index=chunk_index,
                        chunk_type="paragraph",
                        text=chunk_text,
                        table_html=None,
                        page_start=page_start,
                        page_end=page_end,
                        token_count=_count_tokens(chunk_text, self.token_model),
                        content_hash=_content_hash(chunk_text),
                    )
                )
                chunk_index += 1
                # Build overlap from tail of current window
                overlap_tokens = 0
                overlap_window: list[str] = []
                for sent_back in reversed(window):
                    t = _count_tokens(sent_back, self.token_model)
                    if overlap_tokens + t <= self.overlap:
                        overlap_window.insert(0, sent_back)
                        overlap_tokens += t
                    else:
                        break
                window = overlap_window
                window_tokens = overlap_tokens

            window.append(sent)
            window_tokens += sent_tokens
            i += 1

        if window:
            chunk_text = " ".join(window)
            chunks.append(
                ChunkRecord(
                    chunk_id=_deterministic_chunk_id(document_version_id, chunk_index),
                    document_version_id=document_version_id,
                    section_path=section_path,
                    chunk_index=chunk_index,
                    chunk_type="paragraph",
                    text=chunk_text,
                    table_html=None,
                    page_start=page_start,
                    page_end=page_end,
                    token_count=_count_tokens(chunk_text, self.token_model),
                    content_hash=_content_hash(chunk_text),
                )
            )
            chunk_index += 1

        return chunks, chunk_index

    # ------------------------------------------------------------------
    # Table chunking
    # ------------------------------------------------------------------

    def _chunk_table(
        self,
        tbl: ParsedTable,
        section_path: str,
        document_version_id: str,
        chunk_index: int,
    ) -> tuple[list[ChunkRecord], int]:
        """Emit table as single chunk, or split into row-group chunks if too large."""
        chunks: list[ChunkRecord] = []
        tokens = _count_tokens(tbl.text, self.token_model)

        if tokens <= self.target:
            chunks.append(
                ChunkRecord(
                    chunk_id=_deterministic_chunk_id(document_version_id, chunk_index),
                    document_version_id=document_version_id,
                    section_path=section_path,
                    chunk_index=chunk_index,
                    chunk_type="table",
                    text=tbl.text,
                    table_html=tbl.table_html or None,
                    page_start=tbl.page,
                    page_end=tbl.page,
                    token_count=tokens,
                    content_hash=_content_hash(tbl.text),
                )
            )
            chunk_index += 1
            return chunks, chunk_index

        # Table is too large — split by row groups
        row_groups = _split_table_rows(tbl, self.target, self.token_model)
        for group_text, group_html in row_groups:
            chunks.append(
                ChunkRecord(
                    chunk_id=_deterministic_chunk_id(document_version_id, chunk_index),
                    document_version_id=document_version_id,
                    section_path=section_path,
                    chunk_index=chunk_index,
                    chunk_type="table_row_group",
                    text=group_text,
                    table_html=group_html,
                    page_start=tbl.page,
                    page_end=tbl.page,
                    token_count=_count_tokens(group_text, self.token_model),
                    content_hash=_content_hash(group_text),
                )
            )
            chunk_index += 1

        return chunks, chunk_index


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _group_by_section(
    doc: NormalizedDocument,
) -> list[tuple[str, list[tuple[str, int | None]], list[ParsedTable]]]:
    """Group paragraphs and tables by their section_path.

    Returns a list of (section_path, [(para_text, page)], [tables]) tuples
    in reading order.
    """
    # Collect all section_paths in the order they first appear
    seen: dict[str, int] = {}
    order: list[str] = []

    for p in doc.paragraphs:
        path = p.section_path
        if path not in seen:
            seen[path] = len(order)
            order.append(path)

    for t in doc.tables:
        path = t.section_path
        if path not in seen:
            seen[path] = len(order)
            order.append(path)

    # Build groups
    para_map: dict[str, list[tuple[str, int | None]]] = {k: [] for k in order}
    table_map: dict[str, list[ParsedTable]] = {k: [] for k in order}

    for p in doc.paragraphs:
        para_map[p.section_path].append((p.text, p.page))

    for t in doc.tables:
        table_map[t.section_path].append(t)

    return [(path, para_map[path], table_map[path]) for path in order]


def _split_table_rows(
    tbl: ParsedTable, target_tokens: int, token_model: str
) -> list[tuple[str, str]]:
    """Split a large table into row-group (text, html) pairs.

    The header row (first <tr> in table_html) is repeated in every group.
    """
    if not tbl.table_html:
        # No HTML — split plain text by lines
        lines = tbl.text.splitlines()
        if not lines:
            return [(tbl.text, "<table></table>")]
        header = lines[0]
        groups: list[tuple[str, str]] = []
        buffer: list[str] = [header]
        for line in lines[1:]:
            candidate = "\n".join(buffer + [line])
            if _count_tokens(candidate, token_model) > target_tokens and len(buffer) > 1:
                groups.append(("\n".join(buffer), "<table></table>"))
                buffer = [header, line]
            else:
                buffer.append(line)
        if buffer:
            groups.append(("\n".join(buffer), "<table></table>"))
        return groups or [(tbl.text, "<table></table>")]

    # Parse HTML rows
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]

        soup = BeautifulSoup(tbl.table_html, "lxml")
        all_rows = soup.find_all("tr")
        if not all_rows:
            return [(tbl.text, tbl.table_html)]

        header_text = all_rows[0].get_text(separator=" ", strip=True)

        groups: list[tuple[str, str]] = []
        buffer_rows = [all_rows[0]]
        buffer_text_rows = [header_text]

        for row in all_rows[1:]:
            candidate_text = " ".join(
                [r.get_text(separator=" ", strip=True) for r in buffer_rows + [row]]
            )
            if _count_tokens(candidate_text, token_model) > target_tokens and len(buffer_rows) > 1:
                group_html = f"<table>{''.join(str(r) for r in buffer_rows)}</table>"
                group_text = "\n".join(buffer_text_rows)
                groups.append((group_text, group_html))
                # Reset with header
                buffer_rows = [all_rows[0], row]
                buffer_text_rows = [header_text, row.get_text(separator=" ", strip=True)]
            else:
                buffer_rows.append(row)
                buffer_text_rows.append(row.get_text(separator=" ", strip=True))

        if buffer_rows:
            group_html = f"<table>{''.join(str(r) for r in buffer_rows)}</table>"
            group_text = "\n".join(buffer_text_rows)
            groups.append((group_text, group_html))

        return groups or [(tbl.text, tbl.table_html)]

    except ImportError:
        # bs4 not available — fall back to plain-text split
        return [(tbl.text, tbl.table_html)]
