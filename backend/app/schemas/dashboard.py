"""Dashboard API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.incident import IncidentListItem


class DashboardSummaryResponse(BaseModel):
    open_incidents: int
    critical_incidents: int
    active_analyses: int
    resolved_today: int
    failed_deployments: int
    successful_deployments: int
    average_resolution_minutes: float | None
    deployment_success_rate: float | None


class IncidentTrendItem(BaseModel):
    period: str
    incident_count: int
    resolved_count: int


class IncidentTrendResponse(BaseModel):
    interval: str
    items: list[IncidentTrendItem]


class SeverityDistributionResponse(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class FailureCategoryItem(BaseModel):
    category: str
    count: int


class FailureCategoryDistributionResponse(BaseModel):
    items: list[FailureCategoryItem]


class ActiveAnalysisItem(BaseModel):
    id: UUID
    incident_id: UUID
    incident_number: str
    incident_title: str
    status: str
    current_stage: str | None
    progress_percentage: int
    started_at: datetime | None


class ActivityItem(BaseModel):
    id: UUID
    incident_id: UUID
    incident_number: str
    event_type: str
    title: str
    description: str | None
    occurred_at: datetime
    actor_user_id: UUID | None = None


class RecentIncidentsResponse(BaseModel):
    items: list[IncidentListItem]


class ActiveAnalysesResponse(BaseModel):
    items: list[ActiveAnalysisItem]


class ActivityResponse(BaseModel):
    items: list[ActivityItem]
