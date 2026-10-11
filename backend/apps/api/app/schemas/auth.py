"""Pydantic schemas for Authentication endpoints."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Schema for user login credentials."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128, description="User password")


class TokenResponse(BaseModel):
    """Schema for JWT access token response (Rule 6: minimal data exposure)."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
