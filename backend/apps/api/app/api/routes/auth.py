"""Authentication routes: registration, login, and current-user identity."""

import uuid
from datetime import UTC, datetime

from apps.api.app.api.deps import get_current_user, get_session
from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import ConflictException, UnauthorizedException
from apps.api.app.core.rate_limit import rate_limit_login
from apps.api.app.core.security import create_access_token, hash_password, verify_password
from apps.api.app.models.user import User
from apps.api.app.repositories.user_repo import UserRepository
from apps.api.app.schemas.auth import LoginRequest, TokenResponse
from apps.api.app.schemas.user import UserCreate, UserRead
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from packages.schemas.common import RoleType

router = APIRouter()
settings = get_settings()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserRead:
    """Register a new user account.

    Enforces unique email, hashes password with bcrypt, and assigns default VIEWER role.
    Rule 6: Returns minimal UserRead schema without password_hash.
    """
    user_repo = UserRepository(session)
    existing_user = await user_repo.get_by_email(user_in.email)
    if existing_user is not None:
        raise ConflictException("An account with this email already exists")

    # Fetch default VIEWER role
    viewer_role = await user_repo.get_role_by_name(RoleType.VIEWER.value)
    roles = [viewer_role] if viewer_role else []

    hashed_pw = hash_password(user_in.password)
    new_user = User(
        id=uuid.uuid4(),
        email=user_in.email,
        password_hash=hashed_pw,
        full_name=user_in.full_name,
        is_active=True,
        roles=roles,
    )
    created_user = await user_repo.create(new_user)
    await session.commit()

    return UserRead.model_validate(created_user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT access token",
)
async def login(
    credentials: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
    _rl: None = Depends(rate_limit_login),
) -> TokenResponse:
    """Authenticate user with email and password, returning a signed JWT access token.

    Rule 5: Does not reveal via error message whether the email exists.
    Sets HttpOnly, SameSite=Lax cookie for browser session security.
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(credentials.email)

    if user is None or not verify_password(credentials.password, user.password_hash):
        raise UnauthorizedException("Invalid email or password")

    if not user.is_active:
        raise UnauthorizedException("User account is inactive")

    user.last_login_at = datetime.now(UTC)
    await session.commit()

    roles = [role.name for role in user.roles]
    token = create_access_token(subject=user.id, roles=roles)

    # Set HttpOnly, SameSite=Lax cookie for browser session security
    response.set_cookie(
        key="rag_access_token",
        value=token,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=(settings.APP_ENV == "production"),
        path="/",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",  # noqa: S106
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Sign out and invalidate HttpOnly authentication cookie",
)
async def logout(response: Response) -> dict[str, str]:
    """Clear HttpOnly authentication cookie."""
    response.delete_cookie(key="rag_access_token", path="/")
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user identity",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Return the profile and roles of the authenticated caller.

    Rule 6: Minimal data exposure — only fields in UserRead.
    """
    return UserRead.model_validate(current_user)
