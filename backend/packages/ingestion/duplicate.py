"""Duplicate detection across scan batch and PostgreSQL database."""
import uuid
from pathlib import Path

from apps.api.app.repositories.document_repo import DocumentRepository
from sqlalchemy.ext.asyncio import AsyncSession


class DuplicateDetector:
    """Detects duplicates within a scan session and against existing database records."""

    def __init__(self, session: AsyncSession | None = None):
        self.session = session
        self.seen_in_batch: dict[str, Path] = {}

    async def check_duplicate(
        self,
        content_hash: str,
        current_file: Path,
    ) -> tuple[bool, str | None, uuid.UUID | None]:
        """Check if content_hash is already present in this batch or in PostgreSQL.

        Returns (is_duplicate, reason_message, existing_db_id).
        """
        # 1. Check intra-batch duplication
        if content_hash in self.seen_in_batch:
            orig = self.seen_in_batch[content_hash]
            return True, f"Duplicate content in current batch (matches {orig.name})", None

        # 2. Check existing database record
        if self.session is not None:
            repo = DocumentRepository(self.session)
            existing_doc = await repo.get_by_hash(content_hash)
            if existing_doc is not None:
                msg = (
                    f"Already registered in database with ID {existing_doc.id} "
                    f"('{existing_doc.title}')"
                )
                return (
                    True,
                    msg,
                    existing_doc.id,
                )

        # Record this hash in the current batch
        self.seen_in_batch[content_hash] = current_file
        return False, None, None
