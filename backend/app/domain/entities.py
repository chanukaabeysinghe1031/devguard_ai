"""Domain entity dataclasses (framework-agnostic)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class UserEntity:
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class UploadedFileEntity:
    id: UUID
    user_id: UUID
    filename: str
    stored_path: str
    file_type: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    platform: str
    is_processed: bool
    created_at: datetime


@dataclass
class PipelineRunEntity:
    id: UUID
    user_id: UUID
    uploaded_file_id: UUID
    workflow_file_id: UUID | None
    status: str
    platform: str
    pipeline_name: str | None
    job_name: str | None
    started_at: datetime | None
    finished_at: datetime | None
    raw_log_excerpt: str | None
    metadata: dict[str, Any]
    created_at: datetime


@dataclass
class PredictionEntity:
    id: UUID
    pipeline_run_id: UUID
    category_id: UUID
    category_name: str
    model_version_id: UUID | None
    confidence_score: float
    classifier_name: str
    probabilities: dict[str, float]
    created_at: datetime


@dataclass
class EvidenceEntity:
    id: UUID
    pipeline_run_id: UUID
    evidence_type: str
    content: str
    source_location: str | None
    relevance_score: float
    highlight_start: int | None
    highlight_end: int | None
    created_at: datetime


@dataclass
class RecommendationEntity:
    id: UUID
    pipeline_run_id: UUID
    root_cause: str
    explanation: str
    remediation_steps: list[dict[str, Any]]
    risk_level: str
    confidence_score: float
    preventive_actions: list[str]
    future_improvements: list[str]
    llm_model: str
    rag_sources: list[dict[str, Any]]
    created_at: datetime


@dataclass
class AnalysisResultEntity:
    """Aggregated analysis output returned to the API layer."""

    pipeline_run: PipelineRunEntity
    prediction: PredictionEntity | None = None
    evidence: list[EvidenceEntity] = field(default_factory=list)
    recommendation: RecommendationEntity | None = None
