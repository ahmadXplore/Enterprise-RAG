"""Ingestion Job Repository."""
import uuid
from collections.abc import Sequence

from apps.api.app.models.ingestion import IngestionJob
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class IngestionJobRepository(BaseRepository[IngestionJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(IngestionJob, session)

    async def list_by_document(self, document_id: uuid.UUID) -> Sequence[IngestionJob]:
        """Fetch all ingestion jobs for a document."""
        query = (
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_recent(self, limit: int = 50) -> Sequence[IngestionJob]:
        """Fetch recent ingestion jobs across documents."""
        query = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
