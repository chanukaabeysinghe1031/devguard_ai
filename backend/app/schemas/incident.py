"""Incident API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreateRequest(BaseModel):
    project_id: UUID
    pipeline_run_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source: str = Field(min_length=1, max_length=40)
    severity: str
    priority: str | None = None
    environment: str | None = Field(default=None, max_length=50)


class IncidentUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    severity: str | None = None
    priority: str | None = None
    tags: list[str] | None = None


class IncidentStatusChangeRequest(BaseModel):
    status: str
    comment: str | None = None


class IncidentAssignRequest(BaseModel):
    user_id: UUID
    reason: str | None = None


class ProjectSummary(BaseModel):
    id: UUID
    name: str
    key: str | None = None


class PipelineRunSummary(BaseModel):
    id: UUID
    external_run_id: str | None = None
    provider: str | None = None
    workflow_name: str | None = None
    source_url: str | None = None


class AssigneeSummary(BaseModel):
    id: UUID
    email: str
    full_name: str


class LatestAnalysisSummary(BaseModel):
    id: UUID
    status: str
    classification: dict[str, Any] | None = None
    root_cause_summary: str | None = None


class IncidentListItem(BaseModel):
    id: UUID
    incident_number: str
    title: str
    project: ProjectSummary
    severity: str
    status: str
    environment: str | None = None
    predicted_category: str | None = None
    ai_confidence: float | None = None
    detected_at: datetime
    current_assignee: AssigneeSummary | None = None


class IncidentResponse(BaseModel):
    id: UUID
    incident_number: str
    project_id: UUID
    pipeline_run_id: UUID | None = None
    title: str
    description: str | None = None
    source: str
    status: str
    severity: str
    priority: str | None = None
    environment: str | None = None
    detected_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime | None = None
    tags: list[str] | None = None


class IncidentDetailResponse(IncidentResponse):
    project: ProjectSummary
    pipeline_run: PipelineRunSummary | None = None
    latest_analysis: LatestAnalysisSummary | None = None
    current_assignee: AssigneeSummary | None = None


class AcknowledgeResponse(BaseModel):
    success: bool = True
    acknowledged_at: datetime


class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    actor_type: str
    title: str
    description: str | None = None
    occurred_at: datetime
