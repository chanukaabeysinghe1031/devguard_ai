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
    company_name: str | None = None
    description: str | None = None
    website: str | None = None
    industry: str | None = None
    country: str | None = None
    timezone: str = "UTC"
    logo_url: str | None = None
    plan: str
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    company_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=120)
    country: str | None = Field(default=None, max_length=120)
    timezone: str | None = Field(default=None, max_length=80)
    logo_url: str | None = None


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


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field(description="organization_admin|engineer|viewer (owner invite disallowed)")


class InvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    invited_by: UUID | None = None
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None
    invite_url: str | None = None


class InvitationCreatedResponse(InvitationResponse):
    """Includes the one-time raw token for copyable link delivery."""

    token: str
    invite_url: str


class InvitationPreviewResponse(BaseModel):
    organization_name: str
    organization_slug: str
    email: str
    role: str
    status: str
    expires_at: datetime
    is_expired: bool
    user_exists: bool


class AcceptInvitationRequest(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
