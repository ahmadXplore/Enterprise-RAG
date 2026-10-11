import uuid
from collections.abc import Callable

from apps.api.app.core.database import get_db
from apps.api.app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from apps.api.app.core.security import decode_access_token
from apps.api.app.models.document import DocumentAccess
from apps.api.app.models.user import User
from apps.api.app.repositories.document_repo import DocumentRepository
from apps.api.app.repositories.user_repo import UserRepository
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.common import AccessPermission, RoleType

security_scheme = HTTPBearer(auto_error=False)


async def get_session(session: AsyncSession = Depends(get_db)) -> AsyncSession:
    """Provides an AsyncSession per request."""
    return session


async def get_current_user(
    request: Request,
    auth: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Validate JWT access token and return the authenticated User with loaded roles.

    Rule 4 & Rule 5: Reject missing, expired, or invalid tokens.
    Supports both Authorization Bearer headers and HttpOnly cookies.
    """
    token: str | None = None
    if auth and auth.credentials:
        token = auth.credentials
    elif "rag_access_token" in request.cookies:
        token = request.cookies.get("rag_access_token")

    if not token:
        raise UnauthorizedException("Authentication required")

    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedException("Invalid token payload")

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as e:
        raise UnauthorizedException("Invalid token subject") from e

    user_repo = UserRepository(session)
    user = await user_repo.get_with_roles(user_id)
    if user is None:
        raise UnauthorizedException("User not found")
    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    return user


def require_roles(*allowed_roles: RoleType | str) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC).

    Rule 4 & Rule 11: Backend authorization is authoritative.
    """
    target_role_names = {r.value if isinstance(r, RoleType) else str(r) for r in allowed_roles}

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {role.name for role in current_user.roles}
        if not (user_role_names & target_role_names):
            raise ForbiddenException("Permission denied: insufficient role privileges")
        return current_user

    return role_checker


# Specific role dependencies for clean route definition
require_admin = require_roles(RoleType.ADMIN)
require_analyst = require_roles(RoleType.ANALYST, RoleType.ADMIN)
require_viewer = require_roles(RoleType.VIEWER, RoleType.ANALYST, RoleType.ADMIN)


async def check_document_access(
    document_id: uuid.UUID,
    required_permission: AccessPermission,
    current_user: User,
    session: AsyncSession,
) -> bool:
    """Verify document-level access control on the backend (Rule 4, Rule 6, TRD Section 16.1).

    Admins have universal access.
    Other users must have an explicit DocumentAccess grant with sufficient permission level.
    """
    user_roles = {r.name for r in current_user.roles}
    if RoleType.ADMIN.value in user_roles or RoleType.ADMIN in user_roles:
        return True

    # Check that the document actually exists
    doc_repo = DocumentRepository(session)
    doc = await doc_repo.get_by_id(document_id)
    if doc is None:
        raise NotFoundException(f"Document {document_id} not found")

    # Define permission hierarchy: admin > manage > read
    hierarchy = {
        AccessPermission.READ: {"read", "manage", "admin"},
        AccessPermission.MANAGE: {"manage", "admin"},
        AccessPermission.ADMIN: {"admin"},
    }
    perm_val = (
        required_permission.value
        if isinstance(required_permission, AccessPermission)
        else str(required_permission)
    )
    allowed_perm_strings = hierarchy.get(required_permission, {perm_val})

    user_role_ids = [r.id for r in current_user.roles]

    conditions = [DocumentAccess.user_id == current_user.id]
    if user_role_ids:
        conditions.append(DocumentAccess.role_id.in_(user_role_ids))

    query = (
        select(DocumentAccess)
        .where(
            DocumentAccess.document_id == document_id,
            or_(*conditions),
            DocumentAccess.permission.in_(allowed_perm_strings),
        )
        .limit(1)
    )
    result = await session.execute(query)
    access_rule = result.scalar_one_or_none()

    if access_rule is None:
        raise ForbiddenException("Access to this document is denied")

    return True


def get_client_ip(request: Request) -> str:
    """Extract client IP safely from request headers or client host."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
