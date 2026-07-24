"""Pipeline run domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.enums import CiProvider, PipelineRunStatus


@dataclass(slots=True)
class PipelineRunEntity:
    id: UUID | None
    project_id: UUID
    provider: CiProvider
    status: PipelineRunStatus = PipelineRunStatus.QUEUED
    external_run_id: str | None = None
    workflow_name: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    triggered_by: str | None = None
    environment: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    source_url: str | None = None
    raw_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
