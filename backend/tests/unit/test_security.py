"""Unit tests for security utilities (password hashing, JWT, IP hashing)."""
import uuid
from datetime import timedelta

import jwt
import pytest
from apps.api.app.config import get_settings
from apps.api.app.core.exceptions import UnauthorizedException
from apps.api.app.core.security import (
    create_access_token,
    decode_access_token,
    hash_ip,
    hash_password,
    verify_password,
)

settings = get_settings()


class TestPasswordHashing:
    def test_hash_password_creates_bcrypt_hash(self):
        password = "SecurePassword123!"  # noqa: S105
        hashed = hash_password(password)
        assert hashed != password
        assert hashed.startswith("$2b$")

    def test_hash_password_salts_uniquely(self):
        password = "SecurePassword123!"  # noqa: S105
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

    def test_verify_password_success(self):
        password = "CorrectHorseBatteryStaple!"  # noqa: S105
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_wrong_password(self):
        password = "CorrectHorseBatteryStaple!"  # noqa: S105
        hashed = hash_password(password)
        assert verify_password("WrongPassword123!", hashed) is False  # noqa: S105

    def test_verify_password_invalid_hash(self):
        assert verify_password("Password123!", "not-a-valid-bcrypt-hash") is False  # noqa: S105


class TestJWTOperations:
    def test_create_and_decode_access_token(self):
        user_id = uuid.uuid4()
        roles = ["VIEWER", "ANALYST"]
        token = create_access_token(subject=user_id, roles=roles)

        payload = decode_access_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["roles"] == roles
        assert "exp" in payload
        assert "iat" in payload

    def test_expired_token_raises_unauthorized(self):
        user_id = uuid.uuid4()
        token = create_access_token(
            subject=user_id,
            roles=["ADMIN"],
            expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
        )
        with pytest.raises(UnauthorizedException) as exc_info:
            decode_access_token(token)
        assert "expired" in exc_info.value.message.lower()

    def test_invalid_signature_raises_unauthorized(self):
        user_id = uuid.uuid4()
        token = jwt.encode(
            {"sub": str(user_id), "roles": ["ADMIN"]},
            "wrong-secret-key-that-is-at-least-32-bytes-long",  # 32+ bytes to satisfy RFC 7518
            algorithm="HS256",
        )
        with pytest.raises(UnauthorizedException):
            decode_access_token(token)

    def test_missing_sub_raises_unauthorized(self):
        token = jwt.encode(
            {"roles": ["ADMIN"]},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(UnauthorizedException) as exc_info:
            decode_access_token(token)
        assert "subject missing" in exc_info.value.message.lower()


class TestPrivacyHashing:
    def test_hash_ip_sha256(self):
        ip = "192.168.1.100"
        hashed = hash_ip(ip)
        assert len(hashed) == 64
        assert hash_ip(ip) == hashed
        assert "192.168.1.100" not in hashed
