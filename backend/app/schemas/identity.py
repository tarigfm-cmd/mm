import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    username: Optional[str] = Field(default=None, min_length=3, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")


class UserRead(BaseModel):
    id: uuid.UUID
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

ORG_TYPES = {
    "university",
    "pharmacy_chain",
    "hospital",
    "training_center",
    "enterprise",
    "individual_workspace",
}


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    org_type: str = Field(default="individual_workspace")

    @field_validator("org_type")
    @classmethod
    def valid_org_type(cls, v: str) -> str:
        if v not in ORG_TYPES:
            raise ValueError(f"org_type must be one of: {', '.join(sorted(ORG_TYPES))}")
        return v


class OrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    org_type: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Roles & Permissions
# ---------------------------------------------------------------------------

class PermissionRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    resource: str
    action: str
    description: Optional[str]

    model_config = {"from_attributes": True}


class RoleRead(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    is_system_role: bool
    permissions: List[PermissionRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------

class OrganizationMembershipRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID
    is_active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMembershipCreate(BaseModel):
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role_id: uuid.UUID
