"""Enterprise File Security Scanner and Payload Sanitizer.

Guards ingestion against:
1. Corrupted, truncated, or unparseable files
2. Disguised/polyglot files (magic bytes mismatch)
3. PDF embedded malicious JavaScript, Launch actions, and binary payloads
4. Office OpenXML (DOCX/XLSX) VBA macros (vbaProject.bin), OLE objects, and DDE
5. CSV / TSV formula and DDE command injection (=cmd, +cmd, -cmd, @SUM, etc.)
6. Zip decompression bombs (ratio limit)
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


class FileSecurityError(Exception):
    """Raised when a file fails security scanning or contains malicious payloads."""
    pass


@dataclass
class ScanResult:
    is_safe: bool
    sanitized_content: bytes
    detected_threats: list[str]
    file_type: str
    size_bytes: int


class FileSecurityScanner:
    """Scans and sanitizes uploaded documents before parsing or indexing."""

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    MAX_UNCOMPRESSED_RATIO = 100       # Zip bomb protection
    MAX_UNCOMPRESSED_SIZE = 150 * 1024 * 1024  # 150 MB

    # Dangerous PDF object patterns (inspected outside compressed stream bodies)
    PDF_MALICIOUS_PATTERNS = [
        (re.compile(rb"/JavaScript\b"), "Embedded JavaScript action (/JavaScript)"),
        (re.compile(rb"/S\s*/JavaScript\b"), "Embedded JavaScript action (/S /JavaScript)"),
        (re.compile(rb"/Launch\b"), "Executable launch command (/Launch)"),
        (re.compile(rb"/EmbeddedFiles\b"), "Embedded binary file payload (/EmbeddedFiles)"),
        (re.compile(rb"/OpenAction\s*<<[^>]*?/Launch"), "Auto-executing launch on document open"),
        (re.compile(rb"/RichMedia\b"), "Flash/RichMedia active content"),
    ]

    # Dangerous Office OpenXML macro files
    OFFICE_MACRO_FILES = [
        "vbaProject.bin",
        "word/vbaProject.bin",
        "xl/vbaProject.bin",
        "word/embeddings/",
        "xl/embeddings/",
    ]

    @classmethod
    def scan_and_sanitize(cls, content: bytes, filename: str, ext: str) -> ScanResult:
        """Scan file for corruption and malicious content, sanitizing if applicable."""
        threats: list[str] = []
        normalized_ext = ext.lower()

        if not content:
            raise FileSecurityError("File is completely empty (0 bytes).")

        if len(content) > cls.MAX_FILE_SIZE:
            raise FileSecurityError(
                f"File size exceeds maximum allowed threshold of {cls.MAX_FILE_SIZE // (1024*1024)}MB."
            )

        sanitized_bytes = content

        if normalized_ext == ".pdf":
            cls._scan_pdf(content, threats)
        elif normalized_ext in {".docx", ".xlsx"}:
            cls._scan_office_zip(content, normalized_ext, threats)
        elif normalized_ext in {".csv", ".tsv", ".txt"}:
            sanitized_bytes = cls._scan_and_sanitize_tabular_text(content, normalized_ext, threats)
        else:
            raise FileSecurityError(f"Unsupported or unauthorized file extension '{ext}'.")

        if threats:
            raise FileSecurityError(
                f"Security violation: {'; '.join(threats)}"
            )

        return ScanResult(
            is_safe=True,
            sanitized_content=sanitized_bytes,
            detected_threats=threats,
            file_type=normalized_ext,
            size_bytes=len(sanitized_bytes),
        )

    @classmethod
    def _scan_pdf(cls, content: bytes, threats: list[str]) -> None:
        """Validate PDF magic bytes, structural integrity, and scan for executable/script payloads."""
        # 1. Check PDF Magic Header
        if not content.startswith(b"%PDF-"):
            header_idx = content[:1024].find(b"%PDF-")
            if header_idx == -1:
                threats.append("Corrupted or disguised PDF (missing valid '%PDF-' header)")
                return

        # 2. Check EOF marker for truncated/corrupted PDF
        eof_idx = content[-1024:].find(b"%%EOF")
        if eof_idx == -1 and len(content) > 2048:
            if content[-4096:].find(b"%%EOF") == -1:
                threats.append("Truncated or malformed PDF structure (missing '%%EOF' trailer)")

        # 3. Structural validation via PyMuPDF if available
        try:
            import pymupdf
            with pymupdf.open(stream=content, filetype="pdf") as doc:
                if doc.is_encrypted:
                    threats.append("Encrypted or password-protected PDFs cannot be ingested")
                    return
                if doc.embfile_count() > 0:
                    threats.append(f"Embedded binary file payload detected ({doc.embfile_count()} embedded file(s))")
                    return
        except Exception:
            pass

        # 4. Strip binary stream bodies (stream...endstream) so compressed binary data
        # (images, embedded fonts, vector streams) does not trigger false positives
        structural_content = re.sub(rb"(?s)stream\r?\n.*?endstream", b"", content)

        # 5. Scan structural objects for active exploits
        for pattern, description in cls.PDF_MALICIOUS_PATTERNS:
            if pattern.search(structural_content):
                threats.append(f"Malicious active content detected in PDF: {description}")

    @classmethod
    def _scan_office_zip(cls, content: bytes, ext: str, threats: list[str]) -> None:
        """Validate DOCX/XLSX ZIP structure, detect macros, OLE objects, and zip bombs."""
        if not content.startswith(b"PK\x03\x04"):
            threats.append(f"Corrupted or disguised {ext.upper()} archive (invalid ZIP header)")
            return

        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                # 1. Zip bomb verification
                total_uncompressed = 0
                for info in zf.infolist():
                    total_uncompressed += info.file_size
                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > cls.MAX_UNCOMPRESSED_RATIO:
                            threats.append(
                                f"Decompression bomb detected in archive (ratio {ratio:.1f}:1)"
                            )
                            return
                if total_uncompressed > cls.MAX_UNCOMPRESSED_SIZE:
                    threats.append(
                        f"Decompressed archive size exceeds limit ({total_uncompressed // (1024*1024)}MB)"
                    )
                    return

                # 2. Check for valid OpenXML root content types
                file_names = set(zf.namelist())
                if "[Content_Types].xml" not in file_names:
                    threats.append(f"Invalid OpenXML document: missing '[Content_Types].xml'")

                # 3. Scan for VBA Macros, OLE bin files
                for fname in file_names:
                    fname_lower = fname.lower()
                    for macro_marker in cls.OFFICE_MACRO_FILES:
                        if macro_marker in fname_lower:
                            threats.append(
                                f"Forbidden macro/executable component detected: '{fname}'"
                            )
                            return
                    if fname_lower.endswith((".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js")):
                        threats.append(
                            f"Disguised executable/script found inside archive: '{fname}'"
                        )
                        return

                # 4. Check for DDE formula links in workbooks/documents
                for xml_name in ["word/document.xml", "xl/workbook.xml"]:
                    if xml_name in file_names:
                        xml_bytes = zf.read(xml_name)
                        if b"ddeService" in xml_bytes or b"ddeItem" in xml_bytes:
                            threats.append("Dynamic Data Exchange (DDE) external execution trigger detected")
        except zipfile.BadZipFile:
            threats.append(f"Corrupted or unreadable {ext.upper()} archive")

    @classmethod
    def _scan_and_sanitize_tabular_text(
        cls, content: bytes, ext: str, threats: list[str]
    ) -> bytes:
        """Validate text encoding, detect null bytes, and sanitize CSV formula injection."""
        # 1. Check for null bytes (binary smuggling disguised as CSV)
        if b"\x00" in content:
            threats.append("Binary payload or null-byte smuggling detected in text file")
            return content

        # 2. Decode text safely
        text_str = ""
        encoding_used = "utf-8"
        for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252"]:
            try:
                text_str = content.decode(enc)
                encoding_used = enc
                break
            except UnicodeDecodeError:
                continue

        if not text_str:
            threats.append("Unrecognized or corrupted text encoding")
            return content

        if ext not in {".csv", ".tsv"}:
            return content

        # 3. Sanitize CSV / DDE Formula Injection
        # Cells beginning with =, +, -, @, \t, \r can trigger formula execution in spreadsheets
        delimiter = "\t" if ext == ".tsv" else ","
        reader = csv.reader(io.StringIO(text_str), delimiter=delimiter)
        sanitized_rows: list[list[str]] = []
        formula_triggers = ("=", "+", "-", "@", "\t", "\r")
        sanitized_count = 0

        try:
            for row in reader:
                sanitized_row: list[str] = []
                for cell in row:
                    stripped = cell.strip()
                    if stripped.startswith(formula_triggers):
                        # Mitigate formula injection by prepending apostrophe
                        sanitized_row.append(f"'{cell}")
                        sanitized_count += 1
                    else:
                        sanitized_row.append(cell)
                sanitized_rows.append(sanitized_row)
        except Exception:
            # If CSV parsing fails, file may be malformed
            threats.append("Malformed tabular file structure")
            return content

        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        writer.writerows(sanitized_rows)
        return output.getvalue().encode("utf-8")
