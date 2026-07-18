"""Pipeline run domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.enums import PipelineRunStatus


@dataclass(slots=True)
class PipelineRunEntity:
    id: UUID | None
    user_id: UUID
    uploaded_file_id: UUID
    platform: str
    status: PipelineRunStatus = PipelineRunStatus.PENDING
    workflow_file_id: UUID | None = None
    pipeline_name: str | None = None
    job_name: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    raw_log_excerpt: str | None = None
    run_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
