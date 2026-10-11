"""Dataset file scanner and streaming SHA-256 hashing."""
import hashlib
from pathlib import Path


def calculate_sha256(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash streamingly to support large filings without high memory usage."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def scan_directory(
    directory: Path,
    allowed_extensions: set[str] | None = None,
) -> list[Path]:
    """Recursively scan a directory for supported files, preventing path traversal."""
    resolved_dir = directory.resolve()
    if not resolved_dir.is_dir():
        return []

    discovered: list[Path] = []
    for item in resolved_dir.rglob("*"):
        if not item.is_file():
            continue

        # Prevent directory traversal attacks (Rule 13)
        try:
            item.resolve().relative_to(resolved_dir)
        except ValueError:
            continue

        if allowed_extensions is not None:
            if item.suffix.lower() in allowed_extensions:
                discovered.append(item)
        else:
            discovered.append(item)

    discovered.sort()
    return discovered


def get_mime_type(file_path: Path) -> str:
    """Return standard MIME type based on file extension."""
    suffix = file_path.suffix.lower()
    mapping = {
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".json": "application/json",
        ".jsonl": "application/jsonlines",
        ".csv": "text/csv",
    }
    return mapping.get(suffix, "application/octet-stream")
