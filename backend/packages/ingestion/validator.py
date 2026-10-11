"""Corpus validation pipeline (Rule 4, Rule 14: Never silently discard invalid files)."""
from collections import defaultdict
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from packages.ingestion.duplicate import DuplicateDetector
from packages.ingestion.extractor import (
    extract_acord_metadata,
    extract_cuad_metadata,
    extract_educational_metadata,
    extract_maud_metadata,
    extract_sec_metadata,
)
from packages.ingestion.scanner import calculate_sha256
from packages.schemas.common import DocumentSourceType
from packages.schemas.validation import (
    CorpusValidationReport,
    FileValidationResult,
    ValidationStatus,
)


class CorpusValidator:
    """Validates multi-source document collections before registration and ingestion."""

    def __init__(self, session: AsyncSession | None = None):
        self.detector = DuplicateDetector(session)

    async def validate_file(
        self,
        file_path: Path,
        source_type: DocumentSourceType | str,
    ) -> FileValidationResult:
        """Validate an individual file for readability, checksum, duplicates, and metadata."""
        path_str = str(file_path)

        # 1. Check existence and accessibility
        if not file_path.is_file():
            return FileValidationResult(
                file_path=path_str,
                status=ValidationStatus.INVALID,
                error_message="File does not exist or is not a regular file",
            )

        # 2. Check file size (> 0 bytes)
        try:
            size = file_path.stat().st_size
            if size == 0:
                return FileValidationResult(
                    file_path=path_str,
                    status=ValidationStatus.INVALID,
                    error_message="File is empty (0 bytes)",
                )
        except Exception as e:
            return FileValidationResult(
                file_path=path_str,
                status=ValidationStatus.INVALID,
                error_message=f"Failed to stat file: {e}",
            )

        # 3. Compute SHA-256 hash
        try:
            content_hash = calculate_sha256(file_path)
        except Exception as e:
            return FileValidationResult(
                file_path=path_str,
                status=ValidationStatus.INVALID,
                error_message=f"Failed to calculate SHA-256: {e}",
            )

        # 4. Check duplicate detection
        is_dup, dup_reason, _ = await self.detector.check_duplicate(content_hash, file_path)
        if is_dup:
            return FileValidationResult(
                file_path=path_str,
                content_hash=content_hash,
                status=ValidationStatus.DUPLICATE,
                error_message=dup_reason,
            )

        st_val = (
            source_type.value
            if isinstance(source_type, DocumentSourceType)
            else str(source_type).lower()
        )
        try:
            if st_val == DocumentSourceType.SEC.value:
                meta = extract_sec_metadata(file_path)
            elif st_val == DocumentSourceType.CUAD.value:
                meta = extract_cuad_metadata(file_path)
            elif st_val == DocumentSourceType.MAUD.value:
                meta = extract_maud_metadata(file_path)
            elif st_val == DocumentSourceType.ACORD.value:
                meta = extract_acord_metadata(file_path)
            elif st_val in {DocumentSourceType.EDUCATIONAL.value, DocumentSourceType.MANUAL.value, "educational", "manual"}:
                meta = extract_educational_metadata(file_path)
            else:
                return FileValidationResult(
                    file_path=path_str,
                    content_hash=content_hash,
                    status=ValidationStatus.INVALID,
                    error_message=f"Unsupported document source type: '{source_type}'",
                )
        except Exception as e:
            return FileValidationResult(
                file_path=path_str,
                content_hash=content_hash,
                status=ValidationStatus.INVALID,
                error_message=f"Metadata extraction error: {e}",
            )

        return FileValidationResult(
            file_path=path_str,
            content_hash=content_hash,
            status=ValidationStatus.VALID,
            metadata=meta,
        )

    async def validate_collection(
        self,
        files: list[Path],
        source_type: DocumentSourceType | str,
    ) -> CorpusValidationReport:
        """Validate a collection of files and compile an aggregated report."""
        report = CorpusValidationReport(total_scanned=len(files))
        by_source = defaultdict(int)
        by_company = defaultdict(int)
        by_year = defaultdict(int)

        for file_path in files:
            res = await self.validate_file(file_path, source_type)
            if res.status == ValidationStatus.VALID:
                report.valid_count += 1
                report.valid_files.append(res)
                if res.metadata:
                    by_source[res.metadata.source_type] += 1
                    if res.metadata.organization:
                        by_company[res.metadata.organization] += 1
                    if res.metadata.report_year:
                        by_year[res.metadata.report_year] += 1
            elif res.status == ValidationStatus.DUPLICATE:
                report.duplicate_count += 1
                report.duplicates.append(res)
            else:
                report.invalid_count += 1
                report.invalid_files.append(res)

        report.by_source_type = dict(by_source)
        report.by_company = dict(by_company)
        report.by_year = dict(by_year)
        return report
