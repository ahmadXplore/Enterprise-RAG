"""Pydantic schemas for User and Role management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="User password, min 8 characters")
    full_name: str | None = Field(None, max_length=255)


class UserRead(BaseModel):
    """Safe user representation.

    CRITICAL (Rule 6): NEVER include password_hash or internal secrets.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    roles: list[RoleRead] = []
    created_at: datetime
