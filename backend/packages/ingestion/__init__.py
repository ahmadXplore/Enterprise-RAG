"""Ingestion package — document parsing, normalization, and chunking.

Phase 4: Parser abstraction (DoclingParser, UnstructuredFallbackParser, HTMLSpecializedParser)
Phase 5: Normalization + semantic chunking (DocumentNormalizer, SemanticChunker, ChunkStore)
"""
from packages.ingestion.chunk_store import ChunkStore
from packages.ingestion.chunker import ChunkRecord, SemanticChunker
from packages.ingestion.normalizer import DocumentNormalizer
from packages.ingestion.parsed_document import (
    NormalizedDocument,
    ParsedHeading,
    ParsedPage,
    ParsedParagraph,
    ParsedTable,
    ParserProvenance,
)
from packages.ingestion.parser_report import ParserQualityReport, build_report
from packages.ingestion.parsers import (
    DoclingParser,
    HTMLSpecializedParser,
    ParserDispatcher,
    UnstructuredFallbackParser,
)

__all__ = [
    # Document model
    "NormalizedDocument",
    "ParsedHeading",
    "ParsedPage",
    "ParsedParagraph",
    "ParsedTable",
    "ParserProvenance",
    # Parsers
    "DoclingParser",
    "HTMLSpecializedParser",
    "ParserDispatcher",
    "UnstructuredFallbackParser",
    # Quality report
    "ParserQualityReport",
    "build_report",
    # Phase 5
    "ChunkRecord",
    "ChunkStore",
    "DocumentNormalizer",
    "SemanticChunker",
]
