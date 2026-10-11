"""Audit Log Repository."""
import uuid
from collections.abc import Sequence

from apps.api.app.models.audit import AuditLog
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuditLog, session)

    async def list_by_resource(
        self, resource_type: str, resource_id: uuid.UUID | None = None, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs for a specific resource type and optional ID."""
        query = select(AuditLog).where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        query = query.order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()
