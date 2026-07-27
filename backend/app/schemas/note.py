"""Incident note API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NoteCreateRequest(BaseModel):
    note_type: str = Field(min_length=1, max_length=30)
    content: str = Field(min_length=1)
    is_pinned: bool = False


class NoteUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    is_pinned: bool | None = None


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    author_id: UUID
    note_type: str
    content: str
    is_pinned: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
