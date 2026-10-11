"""Security utilities: password hashing, JWT token operations, and privacy hashing."""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import UnauthorizedException

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash plaintext password with bcrypt and automatic salt generation."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plaintext password against bcrypt hash using constant-time comparison."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(
    subject: str | uuid.UUID,
    roles: list[str],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token with user ID and roles."""
    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate signature and expiration of JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if not payload.get("sub"):
            raise UnauthorizedException("Invalid token: subject missing")
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedException("Token has expired") from e
    except jwt.PyJWTError as e:
        raise UnauthorizedException("Could not validate credentials") from e


def hash_ip(ip: str) -> str:
    """Hash client IP address for privacy-safe audit logging (no raw PII/IP)."""
    return hashlib.sha256(ip.strip().encode("utf-8")).hexdigest()
