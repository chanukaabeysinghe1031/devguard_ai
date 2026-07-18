"""User domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.enums import UserRole


@dataclass(slots=True)
class UserEntity:
    id: UUID | None
    email: str
    hashed_password: str
    full_name: str
    role: UserRole
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
