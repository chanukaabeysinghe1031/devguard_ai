"""Incident report API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class ReportGenerateRequest(BaseModel):
    format: str = Field(default="json")
    include_evidence: bool = True
    include_recommendations: bool = True
    include_timeline: bool = True
    include_resolution: bool = True


class ReportGenerateResponse(BaseModel):
    report_id: UUID
    incident_id: UUID
    format: str
    generation_status: str


class ReportListItem(BaseModel):
    id: UUID
    incident_id: UUID
    incident_number: str
    incident_title: str
    format: str
    version: int
    generation_status: str
    created_at: datetime
    generated_by: UUID | None = None


class ReportDetailResponse(BaseModel):
    id: UUID
    incident_id: UUID
    format: str
    version: int
    generation_status: str
    created_at: datetime
    generated_by: UUID | None = None
    download_url: str
    content: dict[str, Any] | None = None


class ReportListResponse(PaginatedResponse[ReportListItem]):
    pass
