"""Prompt injection filter for retrieved document chunks.

Rule 12 — AI/RAG Security: Document content must never be able to hijack LLM
instructions.  This filter is applied AFTER retrieval, BEFORE prompt assembly
so that adversarial text embedded in documents cannot reach the LLM system
prompt context.

Two detection layers:
  1. Regex pattern matching — catches verbatim adversarial phrases.
  2. Pattern-density scoring — catches diluted / obfuscated injections that
     spread phrases across a chunk with padding text.

Dropped chunks are logged server-side only (never returned to the caller).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from packages.retrieval.models import RetrievalResult

logger = logging.getLogger("enterprise_rag")

# ---------------------------------------------------------------------------
# Adversarial pattern library
# Each pattern is compiled case-insensitively and matched against chunk text.
# Patterns are intentionally broad to err on the side of caution.
# ---------------------------------------------------------------------------
_RAW_PATTERNS: list[str] = [
    r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)",
    r"disregard\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)",
    r"forget\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|context)",
    r"override\s+(the\s+)?(system\s+)?prompt",
    r"you\s+are\s+now\s+(a|an|acting\s+as)",
    r"act\s+as\s+(if\s+you\s+are|a|an)\s+(?!the\s+assistant)",
    r"pretend\s+(you\s+are|to\s+be)",
    r"from\s+now\s+on\s+(you\s+are|act|respond)",
    r"new\s+instructions?\s*:",
    r"system\s+prompt\s*:",
    r"your\s+(actual\s+|real\s+|true\s+)?instructions?\s+are",
    r"reveal\s+(your\s+)?(system\s+prompt|instructions?|prompt|rules?)",
    r"print\s+(your\s+)?(system\s+prompt|instructions?)",
    r"output\s+(your\s+)?(system\s+prompt|instructions?)",
    r"what\s+(are|is)\s+your\s+(system\s+prompt|instructions?|prompt)",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode\s+enabled",
    r"enable\s+developer\s+mode",
    r"do\s+anything\s+now",
    r"bypass\s+(all\s+)?(safety|restrictions?|filters?|guidelines?)",
    r"no\s+restrictions?\s+mode",
    r"unrestricted\s+mode",
    r"sudo\s+(mode|command)",
    r"\[SYSTEM\]",
]

_COMPILED_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _RAW_PATTERNS
]

# Maximum allowed adversarial pattern hits per 1 000 characters of chunk text.
# Chunks with density above this threshold are also dropped even if no single
# pattern constitutes a clear injection.
_DEFAULT_MAX_DENSITY: float = 0.5  # 0.5 hits / 1 000 chars


@dataclass
class FilterResult:
    """Outcome of a PromptInjectionFilter.filter() call."""

    kept: list[RetrievalResult]
    dropped_count: int
    audit_entries: list[dict] = field(default_factory=list)


class PromptInjectionFilter:
    """Two-layer prompt injection detector for retrieved document chunks.

    Usage::

        fltr = PromptInjectionFilter()
        result = fltr.filter(chunks)
        safe_chunks = result.kept

    The filter is stateless and thread-safe.
    """

    def __init__(self, max_pattern_density: float = _DEFAULT_MAX_DENSITY) -> None:
        self._max_density = max_pattern_density

    def _score_chunk(self, text: str) -> tuple[int, float]:
        """Return (hit_count, density_per_1000_chars) for a chunk text."""
        hits = sum(1 for p in _COMPILED_PATTERNS if p.search(text))
        char_count = max(len(text), 1)
        density = (hits / char_count) * 1_000
        return hits, density

    def _is_adversarial(self, text: str) -> tuple[bool, str]:
        """Return (is_adversarial, reason) for a single chunk text."""
        hits, density = self._score_chunk(text)
        if hits > 0:
            return True, f"pattern_match hits={hits}"
        if density > self._max_density:
            return True, f"high_density density={density:.3f}"
        return False, ""

    def filter(self, chunks: list[RetrievalResult]) -> FilterResult:
        """Filter *chunks*, returning a FilterResult with only safe chunks.

        Dropped chunks are logged server-side at WARNING level.  The caller
        receives only ``FilterResult.kept``; no adversarial text reaches the
        LLM prompt.
        """
        kept: list[RetrievalResult] = []
        dropped_count = 0
        audit_entries: list[dict] = []

        for chunk in chunks:
            flagged, reason = self._is_adversarial(chunk.text)
            if flagged:
                dropped_count += 1
                entry = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "reason": reason,
                }
                audit_entries.append(entry)
                logger.warning(
                    "Prompt injection detected — chunk dropped before generation",
                    extra={"extra": entry},
                )
            else:
                kept.append(chunk)

        return FilterResult(kept=kept, dropped_count=dropped_count, audit_entries=audit_entries)
