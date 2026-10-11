"""Domain schemas and enums shared across services and packages."""
from enum import StrEnum


class RoleType(StrEnum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class DocumentSourceType(StrEnum):
    SEC = "sec"
    CUAD = "cuad"
    MAUD = "maud"
    ACORD = "acord"
    MANUAL = "manual"
    DOCLAYNET = "doclaynet"
    EDUCATIONAL = "educational"


class DocumentType(StrEnum):
    ANNUAL_REPORT = "annual_report"
    LEGAL_CONTRACT = "legal_contract"
    LEGAL_CLAUSE = "legal_clause"
    LAYOUT_BENCHMARK = "layout_benchmark"
    RESEARCH_PAPER = "research_paper"
    SYLLABUS = "syllabus"
    DATASET = "dataset"
    SPREADSHEET = "spreadsheet"
    EDUCATIONAL = "educational"


class DocumentStatus(StrEnum):
    REGISTERED = "registered"
    PARSING = "parsing"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    READY = "ready"
    FAILED = "failed"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryType(StrEnum):
    DIRECT = "DIRECT"
    COMPARISON = "COMPARISON"
    TEMPORAL = "TEMPORAL"
    NUMERICAL = "NUMERICAL"
    LEGAL = "LEGAL"
    CROSS_DOCUMENT = "CROSS_DOCUMENT"
    UNANSWERABLE = "UNANSWERABLE"


class AccessPermission(StrEnum):
    READ = "read"
    MANAGE = "manage"
    ADMIN = "admin"
