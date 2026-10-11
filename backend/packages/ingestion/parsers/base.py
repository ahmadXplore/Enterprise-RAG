"""BaseParser — abstract base for all document parsers.

Enforces:
- Path-traversal guard (file must be inside an allowed root).
- Uniform parse() interface.
- name / version properties every concrete parser must expose.
"""
from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from packages.ingestion.parsed_document import NormalizedDocument

# Allowed roots for document parsing.  All paths must resolve to a child of one
# of these directories.  PARSED_ROOTS can be overridden in tests by subclassing.
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_ALLOWED_ROOTS: tuple[Path, ...] = (
    (_PROJECT_ROOT / "data").resolve(),
    (_PROJECT_ROOT / "EDUCATIONAL DATA").resolve(),
    (_PROJECT_ROOT / "sec_10k_dataset").resolve(),
    (_PROJECT_ROOT / "legal_datasets").resolve(),
    Path("data").resolve(),
    Path("EDUCATIONAL DATA").resolve(),
    Path(tempfile.gettempdir()).resolve(),
)


def _assert_safe_path(file_path: Path, allowed_roots: tuple[Path, ...] | None = None) -> None:
    """Raise ValueError when file_path is outside every allowed root.

    Prevents path-traversal attacks where a caller could supply e.g.
    ``../../etc/passwd`` as a document path.
    """
    roots = allowed_roots if allowed_roots is not None else _DEFAULT_ALLOWED_ROOTS
    resolved = file_path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return  # inside this root — safe
        except ValueError:
            continue
    # Also allow absolute paths that are explicitly on a different drive/mount
    # used in CI — check via os.path.commonpath as a fallback for Windows.
    for root in roots:
        try:
            if os.path.commonpath([resolved, root]) == str(root):
                return
        except ValueError:
            continue
    raise ValueError(
        f"Path traversal detected: '{file_path}' is outside all allowed parser roots."
    )


class BaseParser(ABC):
    """Abstract base class for all document parsers."""

    # Subclasses must declare these as class attributes or properties.
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def version(self) -> str: ...

    def _check_path(self, file_path: Path) -> None:
        """Run the path-traversal guard. Subclasses may pass extra roots."""
        _assert_safe_path(file_path)

    @abstractmethod
    def parse(
        self, file_path: Path, document_id: str, document_version_id: str
    ) -> NormalizedDocument:
        """Parse *file_path* and return a NormalizedDocument.

        Args:
            file_path: Absolute path to the source file. Must be inside an
                allowed root (enforced by _check_path).
            document_id: UUID string of the Document row.
            document_version_id: UUID string of the DocumentVersion row.

        Returns:
            NormalizedDocument populated with all extractable structure.

        Raises:
            ValueError: If the path is outside allowed roots.
            RuntimeError: If the parser encounters an unrecoverable error.
        """
