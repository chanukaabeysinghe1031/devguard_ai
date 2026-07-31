"""Phase 6A.2 temporal event and localisation result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.artifacts.models import SourceLocation
from app.domain.temporal.enums import (
    TemporalEventType,
    TemporalLinkDerivation,
    TemporalLinkType,
    TemporalLocalisationStatus,
    TemporalOrderingMethod,
    TimestampQuality,
)

HEURISTIC_VERSION = "temporal_heuristics_v1"


@dataclass(slots=False, frozen=False)
class TemporalEvent:
    id: str
    analysis_id: str
    artifact_id: str | None
    event_type: TemporalEventType
    sequence_index: int
    timestamp: datetime | None = None
    workflow_name: str | None = None
    job_name: str | None = None
    step_name: str | None = None
    command: str | None = None
    exit_code: int | None = None
    message: str | None = None
    severity: str = "info"
    source_location: SourceLocation | None = None
    parser_entity_id: str | None = None
    parent_event_id: str | None = None
    is_failure: bool = False
    is_candidate_primary_failure: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    extraction_confidence: float = 0.5
    organization_id: str | None = None
    project_id: str | None = None


@dataclass(slots=False, frozen=False)
class TemporalCausalLink:
    id: str
    source_event_id: str
    target_event_id: str
    link_type: TemporalLinkType
    derivation: TemporalLinkDerivation
    confidence: float
    explanation: str
    supporting_event_ids: list[str] = field(default_factory=list)
    rule_id: str = ""
    rule_version: str = HEURISTIC_VERSION
    # Heuristic links are never "proven causality".
    proven_causality: bool = False


@dataclass(slots=False, frozen=False)
class TemporalLocalisationResult:
    analysis_id: str
    status: TemporalLocalisationStatus
    primary_failure_event_id: str | None = None
    primary_failure_type: str | None = None
    primary_failure_summary: str | None = None
    downstream_symptom_event_ids: list[str] = field(default_factory=list)
    upstream_context_event_ids: list[str] = field(default_factory=list)
    causal_precedence_links: list[TemporalCausalLink] = field(default_factory=list)
    events: list[TemporalEvent] = field(default_factory=list)
    ordering_method: TemporalOrderingMethod = TemporalOrderingMethod.PARSER_SEQUENCE
    timestamp_quality: TimestampQuality = TimestampQuality.ABSENT
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    heuristic_version: str = HEURISTIC_VERSION
    organization_id: str | None = None
    project_id: str | None = None
    incident_id: str | None = None
    artifact_bundle_id: str | None = None
    duration_ms: int | None = None
