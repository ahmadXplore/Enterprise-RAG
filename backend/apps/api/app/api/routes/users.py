"""User management routes (Admin-only RBAC, Rule 4, 6, 11)."""

import uuid
from datetime import UTC, datetime

from apps.api.app.api.deps import get_client_ip, get_session, require_admin
from apps.api.app.core.audit import record_audit_log
from apps.api.app.core.exceptions import ConflictException, NotFoundException
from apps.api.app.core.security import hash_password
from apps.api.app.models.user import User
from apps.api.app.repositories.user_repo import UserRepository
from apps.api.app.schemas.user import (
    AdminUserCreate,
    UserRead,
    UserRoleUpdate,
    UserStatusUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Request, status
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


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account (Admin only)",
)
async def create_user(
    payload: AdminUserCreate,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Create a new user account with specified role and status.

    Admin can assign ADMIN, ANALYST, or VIEWER role directly.
    """
    user_repo = UserRepository(session)
    existing = await user_repo.get_by_email(payload.email)
    if existing is not None:
        raise ConflictException(f"Account with email '{payload.email}' already exists")

    # Match role by name case-insensitively
    target_role = await user_repo.get_role_by_name(payload.role)
    if target_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role}' not recognized. Allowed: ADMIN, ANALYST, VIEWER",
        )

    hashed_pw = hash_password(payload.password)
    user_id = uuid.uuid4()
    new_user = User(
        id=user_id,
        email=payload.email,
        password_hash=hashed_pw,
        full_name=payload.full_name,
        is_active=True,
        roles=[target_role],
    )
    created_user = await user_repo.create(new_user)

    await record_audit_log(
        session=session,
        action="user:create",
        resource_type="user",
        user_id=admin_user.id,
        resource_id=user_id,
        client_ip=get_client_ip(request),
        metadata={
            "created_email": payload.email,
            "assigned_role": target_role.name,
            "full_name": payload.full_name,
        },
    )
    await session.commit()

    return UserRead.model_validate(created_user)


@router.patch(
    "/{user_id}/status",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Block or reinstate a user account (Admin only)",
)
async def update_user_status(
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Block or reinstate user account access.

    Blocking instantly revokes authorization on all subsequent API requests.
    Prevents administrators from blocking their own account.
    """
    if target_user_id := user_id:
        if target_user_id == admin_user.id and not payload.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security policy prevents blocking your own administrative account.",
            )

    user_repo = UserRepository(session)
    target_user = await user_repo.get_with_roles(user_id)
    if target_user is None:
        raise NotFoundException(f"User with ID '{user_id}' not found")

    target_user.is_active = payload.is_active

    action_label = "user:reinstate" if payload.is_active else "user:block"
    await record_audit_log(
        session=session,
        action=action_label,
        resource_type="user",
        user_id=admin_user.id,
        resource_id=user_id,
        client_ip=get_client_ip(request),
        metadata={
            "target_email": target_user.email,
            "new_is_active": payload.is_active,
        },
    )
    await session.commit()

    return UserRead.model_validate(target_user)


@router.patch(
    "/{user_id}/role",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Change user role (Admin only)",
)
async def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdate,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Update assigned role for a user (ADMIN, ANALYST, VIEWER)."""
    user_repo = UserRepository(session)
    target_user = await user_repo.get_with_roles(user_id)
    if target_user is None:
        raise NotFoundException(f"User with ID '{user_id}' not found")

    new_role = await user_repo.get_role_by_name(payload.role)
    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role '{payload.role}' not recognized. Allowed: ADMIN, ANALYST, VIEWER",
        )

    # Protect against admin demoting self
    if user_id == admin_user.id and new_role.name.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security policy prevents revoking your own ADMIN role.",
        )

    target_user.roles = [new_role]

    await record_audit_log(
        session=session,
        action="user:role_update",
        resource_type="user",
        user_id=admin_user.id,
        resource_id=user_id,
        client_ip=get_client_ip(request),
        metadata={
            "target_email": target_user.email,
            "new_role": new_role.name,
        },
    )
    await session.commit()

    return UserRead.model_validate(target_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a user account (Admin only)",
)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    admin_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Permanently delete a user account.

    Cascades deletion to user roles and user conversations.
    Security policy forbids deleting your own logged-in admin account.
    """
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security policy prevents deleting your own administrative account.",
        )

    user_repo = UserRepository(session)
    target_user = await user_repo.get_with_roles(user_id)
    if target_user is None:
        raise NotFoundException(f"User with ID '{user_id}' not found")

    deleted_email = target_user.email
    await user_repo.delete(target_user)

    await record_audit_log(
        session=session,
        action="user:delete",
        resource_type="user",
        user_id=admin_user.id,
        resource_id=user_id,
        client_ip=get_client_ip(request),
        metadata={"deleted_email": deleted_email},
    )
    await session.commit()

    return {
        "message": f"User '{deleted_email}' deleted successfully.",
        "id": str(user_id),
    }
