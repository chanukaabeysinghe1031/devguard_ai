"""Incident history API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.incident import AssigneeSummary, ProjectSummary


class HistoryIncidentItem(BaseModel):
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
    resolved_at: datetime | None = None
    resolution_summary: str | None = None
    root_cause_summary: str | None = None
    current_assignee: AssigneeSummary | None = None
