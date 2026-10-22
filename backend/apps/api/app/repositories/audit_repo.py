"""Audit Log Repository."""
import uuid
from collections.abc import Sequence
from typing import Any

from apps.api.app.models.audit import AuditLog
from apps.api.app.models.user import User
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


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

    async def list_paginated_with_user(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Fetch audit logs with joined user details, supporting filtering and pagination."""
        base = select(AuditLog).options(joinedload(AuditLog.user))
        count_q = select(func.count(AuditLog.id))

        if action:
            base = base.where(AuditLog.action == action)
            count_q = count_q.where(AuditLog.action == action)
        if resource_type:
            base = base.where(AuditLog.resource_type == resource_type)
            count_q = count_q.where(AuditLog.resource_type == resource_type)
        if search:
            search_pattern = f"%{search}%"
            base = base.where(
                AuditLog.action.ilike(search_pattern)
                | AuditLog.resource_type.ilike(search_pattern)
            )
            count_q = count_q.where(
                AuditLog.action.ilike(search_pattern)
                | AuditLog.resource_type.ilike(search_pattern)
            )

        total_res = await self.session.execute(count_q)
        total = total_res.scalar_one()

        query = base.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(query)
        logs = result.scalars().all()

        items = []
        for log in logs:
            items.append({
                "id": str(log.id),
                "user_id": str(log.user_id) if log.user_id else None,
                "user_email": log.user.email if log.user else "System",
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "ip_hash": log.ip_hash,
                "metadata": log.metadata_,
                "created_at": log.created_at.isoformat(),
            })
        return items, total
