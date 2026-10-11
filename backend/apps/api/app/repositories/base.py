"""Base generic repository for async SQLAlchemy operations."""
import uuid
from collections.abc import Sequence
from typing import Generic, TypeVar

from apps.api.app.models.base import Base
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository providing standardized async CRUD operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: uuid.UUID) -> ModelType | None:
        """Fetch a single record by primary key."""
        return await self.session.get(self.model, id)

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelType]:
        """Fetch a page of records."""
        query = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, instance: ModelType) -> ModelType:
        """Add and flush a new record."""
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Remove a record."""
        await self.session.delete(instance)
        await self.session.flush()
