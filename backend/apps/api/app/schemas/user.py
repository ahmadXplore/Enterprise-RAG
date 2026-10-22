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
    age: int | None = Field(None, ge=1, le=120, description="User age in years")


class UserRead(BaseModel):
    """Safe user representation.

    CRITICAL (Rule 6): NEVER include password_hash or internal secrets.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str | None = None
    age: int | None = None
    is_active: bool
    roles: list[RoleRead] = []
    created_at: datetime


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="User password, min 8 characters")
    full_name: str | None = Field(None, max_length=255)
    role: str = Field("VIEWER", description="Assigned role: ADMIN, ANALYST, VIEWER")


class UserStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="Active or blocked status")


class UserRoleUpdate(BaseModel):
    role: str = Field(..., description="Role to assign: ADMIN, ANALYST, VIEWER")

