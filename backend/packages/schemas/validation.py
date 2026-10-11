"""Schemas for dataset validation, metadata extraction, and corpus reporting."""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(StrEnum):
    VALID = "valid"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class ExtractedMetadata(BaseModel):
    """Normalized document metadata extracted prior to database registration."""
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1)
    organization: str | None = None
    ticker: str | None = None
    report_year: int | None = None
    filing_date: str | None = None
    report_date: str | None = None
    accession_number: str | None = None
    source_uri: str | None = None
    original_filename: str
    mime_type: str | None = None
    file_size: int = 0
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class FileValidationResult(BaseModel):
    """Validation outcome for an individual file (Rule 14: no silent discards)."""
    file_path: str
    content_hash: str | None = None
    status: ValidationStatus
    error_message: str | None = None
    metadata: ExtractedMetadata | None = None


class CorpusValidationReport(BaseModel):
    """Comprehensive validation summary for a multi-corpus ingestion run."""
    total_scanned: int = 0
    valid_count: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    by_source_type: dict[str, int] = Field(default_factory=dict)
    by_company: dict[str, int] = Field(default_factory=dict)
    by_year: dict[int, int] = Field(default_factory=dict)
    duplicates: list[FileValidationResult] = Field(default_factory=list)
    invalid_files: list[FileValidationResult] = Field(default_factory=list)
    valid_files: list[FileValidationResult] = Field(default_factory=list)
