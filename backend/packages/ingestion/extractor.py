"""Metadata extraction for SEC 10-K, CUAD, MAUD, and ACORD documents."""
import json
from pathlib import Path

from packages.ingestion.scanner import get_mime_type
from packages.schemas.common import DocumentSourceType, DocumentType
from packages.schemas.validation import ExtractedMetadata


def extract_sec_metadata(file_path: Path) -> ExtractedMetadata:
    """Extract metadata for SEC 10-K filing from adjacent metadata.json or directory structure."""
    meta_json_path = file_path.parent / "metadata.json"
    data = {}
    if meta_json_path.is_file():
        try:
            with open(meta_json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to read metadata.json at {meta_json_path}: {e}") from e

    # Fallback to directory structure: <company>/<year>/filing.html
    company = data.get("company")
    if not company:
        # e.g., sec_10k_dataset/apple/2024/filing.html
        company = file_path.parent.parent.name.replace("_", " ").title()

    ticker = data.get("ticker")
    year_raw = data.get("year")
    if year_raw is None:
        try:
            year_raw = int(file_path.parent.name)
        except ValueError:
            year_raw = None

    if year_raw is None:
        raise ValueError(f"Missing report year for SEC filing: {file_path}")

    try:
        report_year = int(year_raw)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid non-integer year '{year_raw}' in {file_path}") from e

    if report_year < 2010 or report_year > 2030:
        raise ValueError(
            f"Invalid fiscal year {report_year} out of realistic range for {file_path}"
        )

    title = f"{company} FY{report_year} Form 10-K"
    primary_doc = data.get("primary_document") or file_path.name

    return ExtractedMetadata(
        title=title,
        source_type=DocumentSourceType.SEC.value,
        document_type=DocumentType.ANNUAL_REPORT.value,
        organization=company,
        ticker=ticker,
        report_year=report_year,
        filing_date=data.get("filing_date"),
        report_date=data.get("report_date"),
        accession_number=data.get("accession_number"),
        source_uri=data.get("source_url") or str(file_path),
        original_filename=primary_doc,
        mime_type=get_mime_type(file_path),
        file_size=file_path.stat().st_size,
        extra_metadata={
            "cik": data.get("cik"),
            "form": data.get("form", "10-K"),
            "source": data.get("source", "SEC EDGAR"),
        },
    )


def extract_cuad_metadata(file_path: Path) -> ExtractedMetadata:
    """Extract metadata for CUAD commercial contract from filename."""
    stem = file_path.stem
    parts = stem.split("-")
    if len(parts) > 1:
        org_part = parts[0].replace("_", " ").strip()
        agreement_type = parts[-1].replace("_", " ").strip()
        title = f"{org_part} — {agreement_type}"
    else:
        title = stem.replace("_", " ").strip()
        org_part = title.split()[0] if title.split() else "Commercial Party"

    return ExtractedMetadata(
        title=title,
        source_type=DocumentSourceType.CUAD.value,
        document_type=DocumentType.LEGAL_CONTRACT.value,
        organization=org_part,
        ticker=None,
        report_year=None,
        source_uri=str(file_path),
        original_filename=file_path.name,
        mime_type=get_mime_type(file_path),
        file_size=file_path.stat().st_size,
        extra_metadata={"dataset": "CUAD_v1"},
    )


def extract_maud_metadata(file_path: Path) -> ExtractedMetadata:
    """Extract metadata for MAUD merger agreement."""
    # Attempt to extract descriptive title from the first lines of contract text
    title = f"MAUD Merger Agreement ({file_path.stem})"
    org = "Merger Parties"
    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            header_lines = [line.strip() for _ in range(30) if (line := f.readline().strip())]
            header_text = " ".join(header_lines)
            if "AGREEMENT AND PLAN OF MERGER" in header_text.upper():
                title = f"Agreement and Plan of Merger ({file_path.stem})"
    except OSError:
        pass  # Fall back to default title if file cannot be read

    return ExtractedMetadata(
        title=title,
        source_type=DocumentSourceType.MAUD.value,
        document_type=DocumentType.LEGAL_CONTRACT.value,
        organization=org,
        ticker=None,
        report_year=None,
        source_uri=str(file_path),
        original_filename=file_path.name,
        mime_type=get_mime_type(file_path),
        file_size=file_path.stat().st_size,
        extra_metadata={"dataset": "MAUD_v1"},
    )


def extract_acord_metadata(file_path: Path) -> ExtractedMetadata:
    """Extract metadata for ACORD clause retrieval dataset."""
    return ExtractedMetadata(
        title="ACORD Legal Clause Retrieval Benchmark Corpus",
        source_type=DocumentSourceType.ACORD.value,
        document_type=DocumentType.LEGAL_CLAUSE.value,
        organization="The Atticus Project",
        ticker=None,
        report_year=None,
        source_uri=str(file_path),
        original_filename=file_path.name,
        mime_type=get_mime_type(file_path),
        file_size=file_path.stat().st_size,
        extra_metadata={"dataset": "ACORD_v1"},
    )


def extract_educational_metadata(
    file_path: Path,
    custom_title: str | None = None,
    custom_org: str | None = None,
    custom_doc_type: str | None = None,
) -> ExtractedMetadata:
    """Extract metadata for educational documents, research papers, datasets, and spreadsheets."""
    import re
    stem = file_path.stem
    clean_title = custom_title or stem.replace("_", " ").replace(" - ", " — ").strip()[:180]

    org = custom_org
    if not org:
        lower_name = file_path.name.lower()
        if "mit" in lower_name:
            org = "MIT"
        elif "stanford" in lower_name:
            org = "Stanford University"
        elif "harvard" in lower_name:
            org = "Harvard University"
        elif "berkeley" in lower_name:
            org = "UC Berkeley"
        elif "cmu" in lower_name:
            org = "Carnegie Mellon University"
        elif "oxford" in lower_name:
            org = "University of Oxford"
        elif "cambridge" in lower_name:
            org = "University of Cambridge"
        elif "worldbank" in lower_name or "wb_" in lower_name:
            org = "World Bank"
        elif "oecd" in lower_name:
            org = "OECD"
        elif "unesco" in lower_name:
            org = "UNESCO"
        elif "nces" in lower_name:
            org = "NCES"
        elif "nsf" in lower_name:
            org = "National Science Foundation"
        elif "uci" in lower_name:
            org = "UCI Machine Learning Repository"
        elif "owid" in lower_name:
            org = "Our World in Data"
        elif "kaggle" in lower_name:
            org = "Kaggle Academic Research"
        elif "eric" in lower_name:
            org = "ERIC Education Database"
        elif "nber" in lower_name:
            org = "NBER"
        else:
            org = "Academic Institution"

    doc_type = custom_doc_type
    if not doc_type:
        lower_name = file_path.name.lower()
        suffix = file_path.suffix.lower()
        if "syllabus" in lower_name:
            doc_type = DocumentType.SYLLABUS.value
        elif "paper" in lower_name or suffix == ".pdf" or "ai_ml" in lower_name or "arxiv" in lower_name:
            doc_type = DocumentType.RESEARCH_PAPER.value
        elif suffix == ".csv":
            doc_type = DocumentType.DATASET.value
        elif suffix in {".xlsx", ".xls"}:
            doc_type = DocumentType.SPREADSHEET.value
        else:
            doc_type = DocumentType.EDUCATIONAL.value

    year_match = re.search(r"\b(19\d\d|20[0-3]\d)\b", stem)
    report_year = int(year_match.group(1)) if year_match else None

    return ExtractedMetadata(
        title=clean_title,
        source_type=DocumentSourceType.EDUCATIONAL.value,
        document_type=doc_type,
        organization=org,
        ticker=None,
        report_year=report_year,
        source_uri=str(file_path),
        original_filename=file_path.name,
        mime_type=get_mime_type(file_path),
        file_size=file_path.stat().st_size,
        extra_metadata={"format": file_path.suffix.lstrip(".").lower()},
    )
