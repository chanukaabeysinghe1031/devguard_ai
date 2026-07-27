"""Pipeline run API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunCreateRequest(BaseModel):
    external_run_id: str | None = Field(default=None, max_length=255)
    provider: str
    workflow_name: str | None = Field(default=None, max_length=255)
    branch: str | None = Field(default=None, max_length=255)
    commit_sha: str | None = Field(default=None, max_length=100)
    triggered_by: str | None = Field(default=None, max_length=255)
    environment: str | None = Field(default=None, max_length=50)
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    source_url: str | None = None
    raw_metadata: dict[str, Any] | None = None


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    external_run_id: str | None = None
    provider: str
    workflow_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    triggered_by: str | None = None
    environment: str | None = None
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    source_url: str | None = None
    incident_count: int = 0
    created_at: datetime | None = None
