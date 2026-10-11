"""Document Access Repository."""
import uuid
from collections.abc import Sequence

from apps.api.app.models.document import DocumentAccess
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class DocumentAccessRepository(BaseRepository[DocumentAccess]):
    def __init__(self, session: AsyncSession):
        super().__init__(DocumentAccess, session)

    async def list_by_document(self, document_id: uuid.UUID) -> Sequence[DocumentAccess]:
        """Fetch all access control rules for a specific document."""
        query = select(DocumentAccess).where(DocumentAccess.document_id == document_id)
        result = await self.session.execute(query)
        return result.scalars().all()
