"""User domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import PlatformRole


@dataclass(slots=True)
class UserEntity:
    id: UUID | None
    email: str
    password_hash: str
    full_name: str
    platform_role: PlatformRole = PlatformRole.NONE
    avatar_url: str | None = None
    is_active: bool = True
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
