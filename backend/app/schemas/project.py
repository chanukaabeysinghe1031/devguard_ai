"""Project API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    key: str = Field(min_length=1, max_length=30)
    description: str | None = None
    repository_url: str | None = None
    default_branch: str | None = Field(default=None, max_length=120)
    ci_provider: str
    cloud_provider: str | None = Field(default=None, max_length=50)
    default_environment: str | None = Field(default=None, max_length=50)


class ProjectUpdateRequest(BaseModel):
    description: str | None = None
    repository_url: str | None = None
    default_branch: str | None = Field(default=None, max_length=120)
    cloud_provider: str | None = Field(default=None, max_length=50)
    default_environment: str | None = Field(default=None, max_length=50)


class ProjectStatistics(BaseModel):
    total_pipeline_runs: int = 0
    failed_pipeline_runs: int = 0
    open_incidents: int = 0
    resolved_incidents: int = 0


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str
    ci_provider: str
    cloud_provider: str | None = None
    status: str
    open_incident_count: int = 0
    last_pipeline_run_at: datetime | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    key: str
    description: str | None = None
    repository_url: str | None = None
    default_branch: str | None = None
    ci_provider: str
    cloud_provider: str | None = None
    default_environment: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectDetailResponse(ProjectResponse):
    statistics: ProjectStatistics = Field(default_factory=ProjectStatistics)
