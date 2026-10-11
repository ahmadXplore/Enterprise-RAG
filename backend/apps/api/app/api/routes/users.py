"""User management routes (Admin-only RBAC, Rule 4, 6, 11)."""

from apps.api.app.api.deps import get_client_ip, get_session, require_admin
from apps.api.app.core.audit import record_audit_log
from apps.api.app.models.user import User
from apps.api.app.repositories.user_repo import UserRepository
from apps.api.app.schemas.user import UserRead
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.get(
    "",
    response_model=list[UserRead],
    status_code=status.HTTP_200_OK,
    summary="List all users (Admin only)",
)
async def list_users(
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[UserRead]:
    """List all registered users.

    Rule 4 & 11: Restricted strictly to ADMIN role.
    Audit logs the privileged access.
    """
    user_repo = UserRepository(session)
    users = await user_repo.list_all(limit=100)

    # Audit log the administrative user list inspection
    await record_audit_log(
        session=session,
        action="user:list",
        resource_type="user",
        user_id=admin_user.id,
        client_ip=get_client_ip(request),
        metadata={"count": len(users)},
    )
    await session.commit()

    return [UserRead.model_validate(u) for u in users]
