"""Resolution API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResolveIncidentRequest(BaseModel):
    resolution_summary: str = Field(min_length=1)
    confirmed_root_cause: str = Field(min_length=1)
    resolution_steps: list[str] = Field(default_factory=list)
    prevention_actions: list[str] = Field(default_factory=list)
    time_spent_minutes: int | None = Field(default=None, ge=0)
    ai_recommendation_used: bool | None = None


class ReopenIncidentRequest(BaseModel):
    reason: str = Field(min_length=1)


class ResolutionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resolution_summary: str
    confirmed_root_cause: str
    resolution_steps: list[str] | None = None
    prevention_actions: list[str] | None = None
    time_spent_minutes: int | None = None
    ai_recommendation_used: bool | None = None
    created_at: datetime | None = None


class ResolveIncidentResponse(BaseModel):
    incident_id: UUID
    status: str
    resolved_at: datetime
    resolution: ResolutionSummary


class ReopenIncidentResponse(BaseModel):
    incident_id: UUID
    status: str
    message: str
