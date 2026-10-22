"""User and Role repository."""
import uuid
from collections.abc import Sequence

from apps.api.app.models.user import Role, User
from apps.api.app.repositories.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch user by unique email address case-insensitively."""
        query = select(User).where(User.email.ilike(email.strip())).options(selectinload(User.roles))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: uuid.UUID) -> User | None:
        """Fetch user with eager-loaded roles."""
        query = select(User).where(User.id == user_id).options(selectinload(User.roles))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_role_by_name(self, name: str) -> Role | None:
        """Fetch role by name (e.g., ADMIN, ANALYST, VIEWER) case-insensitively."""
        query = select(Role).where(Role.name.ilike(name))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_roles(self) -> Sequence[Role]:
        """List all defined roles."""
        query = select(Role)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[User]:
        """Fetch all users ordered by creation date."""
        query = (
            select(User)
            .options(selectinload(User.roles))
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

