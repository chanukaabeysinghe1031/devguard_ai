"""Organization API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    joined_at: datetime


class AddMembershipRequest(BaseModel):
    email: EmailStr
    role: str = Field(description="organization_owner|organization_admin|engineer|viewer")


class UpdateMembershipRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
