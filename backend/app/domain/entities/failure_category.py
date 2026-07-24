"""Failure category domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class FailureCategoryEntity:
    id: UUID | None
    name: str
    code: str
    description: str | None
    is_active: bool = True
    created_at: datetime | None = None
