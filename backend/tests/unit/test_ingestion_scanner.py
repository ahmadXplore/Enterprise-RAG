"""Unit tests for dataset scanner, metadata extractors, and duplicate detector."""
import json
from pathlib import Path

import pytest

from packages.ingestion.duplicate import DuplicateDetector
from packages.ingestion.extractor import (
    extract_acord_metadata,
    extract_cuad_metadata,
    extract_maud_metadata,
    extract_sec_metadata,
)
from packages.ingestion.scanner import calculate_sha256, get_mime_type, scan_directory
from packages.ingestion.validator import CorpusValidator
from packages.schemas.common import DocumentSourceType, DocumentType
from packages.schemas.validation import ValidationStatus


class TestScanner:
    def test_calculate_sha256(self, tmp_path):
        test_file = tmp_path / "sample.txt"
        test_file.write_text("Enterprise RAG Benchmark Corpus", encoding="utf-8")
        h1 = calculate_sha256(test_file)
        assert len(h1) == 64
        assert h1 == calculate_sha256(test_file)

    def test_scan_directory_filters_extensions(self, tmp_path):
        (tmp_path / "file1.html").write_text("html content", encoding="utf-8")
        (tmp_path / "file2.txt").write_text("txt content", encoding="utf-8")
        (tmp_path / "file3.ignore").write_text("ignore me", encoding="utf-8")

        res = scan_directory(tmp_path, allowed_extensions={".html"})
        assert len(res) == 1
        assert res[0].name == "file1.html"

    def test_get_mime_type(self):
        assert get_mime_type(Path("doc.html")) == "text/html"
        assert get_mime_type(Path("doc.pdf")) == "application/pdf"
        assert get_mime_type(Path("doc.txt")) == "text/plain"
        assert get_mime_type(Path("doc.jsonl")) == "application/jsonlines"


class TestMetadataExtractors:
    def test_extract_sec_metadata_from_json(self, tmp_path):
        year_dir = tmp_path / "apple" / "2024"
        year_dir.mkdir(parents=True)
        filing_file = year_dir / "filing.html"
        filing_file.write_text("<html>Apple 10-K Content</html>", encoding="utf-8")

        meta_file = year_dir / "metadata.json"
        meta_data = {
            "company": "Apple Inc.",
            "ticker": "AAPL",
            "cik": "0000320193",
            "year": 2024,
            "form": "10-K",
            "filing_date": "2024-11-01",
            "report_date": "2024-09-28",
            "accession_number": "0000320193-24-000123",
            "primary_document": "aapl-20240928.htm",
            "source_url": "https://sec.gov/aapl.htm",
        }
        meta_file.write_text(json.dumps(meta_data), encoding="utf-8")

        meta = extract_sec_metadata(filing_file)
        assert meta.title == "Apple Inc. FY2024 Form 10-K"
        assert meta.organization == "Apple Inc."
        assert meta.ticker == "AAPL"
        assert meta.report_year == 2024
        assert meta.source_type == DocumentSourceType.SEC.value
        assert meta.document_type == DocumentType.ANNUAL_REPORT.value
        assert meta.original_filename == "aapl-20240928.htm"
        assert meta.source_uri == "https://sec.gov/aapl.htm"

    def test_extract_sec_metadata_rejects_invalid_year(self, tmp_path):
        year_dir = tmp_path / "apple" / "1980"
        year_dir.mkdir(parents=True)
        filing_file = year_dir / "filing.html"
        filing_file.write_text("content", encoding="utf-8")
        meta_file = year_dir / "metadata.json"
        meta_file.write_text(json.dumps({"company": "Apple", "year": 1980}), encoding="utf-8")

        with pytest.raises(ValueError) as exc:
            extract_sec_metadata(filing_file)
        assert "Invalid fiscal year" in str(exc.value)

    def test_extract_cuad_metadata(self, tmp_path):
        contract_file = tmp_path / "AbilityInc_06_15_2020-EX-4.25-SERVICES AGREEMENT.txt"
        contract_file.write_text("Agreement content", encoding="utf-8")

        meta = extract_cuad_metadata(contract_file)
        assert "SERVICES AGREEMENT" in meta.title
        assert meta.source_type == DocumentSourceType.CUAD.value
        assert meta.document_type == DocumentType.LEGAL_CONTRACT.value
        assert meta.original_filename == contract_file.name

    def test_extract_maud_metadata(self, tmp_path):
        contract_file = tmp_path / "contract_0.txt"
        contract_file.write_text(
            "Exhibit 2.1\nAGREEMENT AND PLAN OF MERGER BY AND AMONG CISCO SYSTEMS\n",
            encoding="utf-8",
        )
        meta = extract_maud_metadata(contract_file)
        assert meta.source_type == DocumentSourceType.MAUD.value
        assert meta.document_type == DocumentType.LEGAL_CONTRACT.value
        assert "Merger" in meta.title

    def test_extract_acord_metadata(self, tmp_path):
        corpus_file = tmp_path / "corpus.jsonl"
        corpus_file.write_text('{"_id": "1", "text": "clause"}', encoding="utf-8")
        meta = extract_acord_metadata(corpus_file)
        assert meta.source_type == DocumentSourceType.ACORD.value
        assert meta.document_type == DocumentType.LEGAL_CLAUSE.value


class TestDuplicateAndValidator:
    @pytest.mark.asyncio
    async def test_duplicate_detector_in_batch(self, tmp_path):
        f1 = tmp_path / "doc1.txt"
        f2 = tmp_path / "doc2.txt"
        f1.write_text("Identical Content", encoding="utf-8")
        f2.write_text("Identical Content", encoding="utf-8")

        h1 = calculate_sha256(f1)
        h2 = calculate_sha256(f2)

        detector = DuplicateDetector()
        is_dup1, _, _ = await detector.check_duplicate(h1, f1)
        assert is_dup1 is False

        is_dup2, reason, _ = await detector.check_duplicate(h2, f2)
        assert is_dup2 is True
        assert "doc1.txt" in reason

    @pytest.mark.asyncio
    async def test_validator_rejects_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("", encoding="utf-8")

        validator = CorpusValidator()
        res = await validator.validate_file(empty_file, DocumentSourceType.CUAD)
        assert res.status == ValidationStatus.INVALID
        assert "empty" in res.error_message.lower()
