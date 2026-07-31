"""Phase 6A domain dataclasses for artifact bundles and structured parse results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

from app.domain.artifacts.enums import (
    AcquisitionStatus,
    ArtifactKind,
    ArtifactSource,
    ParseStatus,
    RedactionStatus,
)

DiagnosticSeverity = Literal["info", "warning", "error"]


def content_sha256(text: str) -> str:
    """Return the hex SHA-256 digest of UTF-8 encoded text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=False, frozen=False)
class SourceLocation:
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None


@dataclass(slots=False, frozen=False)
class GraphEntityPreview:
    id: str
    type: str
    label: str
    location: SourceLocation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=False, frozen=False)
class GraphRelationshipPreview:
    source_id: str
    target_id: str
    type: str
    confidence: float = 1.0
    explanation: str | None = None
    deterministic: bool = True


@dataclass(slots=False, frozen=False)
class EvidenceCandidate:
    kind: str
    text: str
    location: SourceLocation | None = None
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=False, frozen=False)
class DiagnosticMessage:
    severity: DiagnosticSeverity
    code: str
    message: str
    location: SourceLocation | None = None


@dataclass(slots=False, frozen=False)
class StructuredParseResult:
    parser_name: str
    parser_version: str
    status: ParseStatus
    entities: list[GraphEntityPreview] = field(default_factory=list)
    relationships: list[GraphRelationshipPreview] = field(default_factory=list)
    diagnostics: list[DiagnosticMessage] = field(default_factory=list)
    evidence_candidates: list[EvidenceCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    extraction_quality: float | None = None
    raw_summary: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=False, frozen=False)
class ArtifactRecord:
    id: str
    kind: ArtifactKind
    source: ArtifactSource
    filename: str
    content_hash: str
    content: str | None = None
    acquisition_status: AcquisitionStatus = AcquisitionStatus.COLLECTED
    redaction_status: RedactionStatus = RedactionStatus.PENDING
    uploaded_file_id: str | None = None
    source_uri: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    parser_version: str | None = None


@dataclass(slots=False, frozen=False)
class AcquisitionError:
    artifact_kind: ArtifactKind | str
    code: str
    message: str


@dataclass(slots=False, frozen=False)
class IncidentArtifactBundle:
    incident_id: str
    organization_id: str
    project_id: str | None = None
    pipeline_run_id: str | None = None
    analysis_run_id: str | None = None
    provider: str | None = None
    repository: str | None = None
    commit_sha: str | None = None
    branch: str | None = None
    workflow_name: str | None = None
    workflow_run_id: str | None = None
    workflow_run_attempt: int | None = None
    failed_job: str | None = None
    failed_step: str | None = None
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    available_artifacts: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    artifact_collection_errors: list[AcquisitionError] = field(default_factory=list)
    artifact_quality_scores: dict[str, Any] = field(default_factory=dict)
    redaction_summary: dict[str, Any] = field(default_factory=dict)
