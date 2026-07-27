"""Analysis run initiation API schemas (no AI execution in Module 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalysisOptions(BaseModel):
    enable_rag: bool = True
    generate_recommendations: bool = True
    top_k_predictions: int = Field(default=3, ge=1, le=10)


class StartAnalysisRequest(BaseModel):
    analysis_type: str = Field(default="full", max_length=40)
    file_ids: list[UUID] = Field(default_factory=list)
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ReanalyseRequest(BaseModel):
    reason: str = Field(min_length=1)
    file_ids: list[UUID] = Field(default_factory=list)


class AnalysisAcceptedResponse(BaseModel):
    analysis_run_id: UUID
    incident_id: UUID
    status: str
    progress_percentage: int = 0
    created_at: datetime


class AnalysisStageResponse(BaseModel):
    name: str
    status: str
    duration_ms: int | None = None


class AnalysisStatusResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    current_stage: str | None = None
    progress_percentage: int
    started_at: datetime | None = None
    estimated_remaining_seconds: int | None = None
    stages: list[AnalysisStageResponse] = Field(default_factory=list)


class AnalysisRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    status: str
    analysis_type: str
    progress_percentage: int
    created_at: datetime | None = None
    completed_at: datetime | None = None


class AnalysisRunDetailResponse(BaseModel):
    id: UUID
    incident_id: UUID
    status: str
    analysis_type: str
    duration_ms: int | None = None
    progress_percentage: int
    current_stage: str | None = None
    input_summary: dict[str, Any] | None = None
    output_summary: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None
