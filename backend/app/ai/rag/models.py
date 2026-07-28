"""Module 9 typed retrieval domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.ai.orchestration.models import clamp01


class RetrievalMode(StrEnum):
    EMBEDDING_ONLY = "embedding_only"
    HYBRID_STATIC = "hybrid_static"
    HYBRID_WITH_HISTORY = "hybrid_with_history"
    KEYWORD_ONLY = "keyword_only"


class RetrievalSourceType(StrEnum):
    KNOWLEDGE_DOCUMENT = "knowledge_document"
    HISTORICAL_INCIDENT = "historical_incident"
    RUNBOOK = "runbook"
    ARCHITECTURE_DOCUMENT = "architecture_document"
    VENDOR_DOCUMENTATION = "vendor_documentation"
    INTERNAL_RESOLUTION = "internal_resolution"


def parse_retrieval_mode(
    value: str | None,
    *,
    default: RetrievalMode = RetrievalMode.HYBRID_STATIC,
) -> RetrievalMode:
    if value is None:
        return default
    try:
        return RetrievalMode(str(value))
    except ValueError as exc:
        raise ValueError(f"Unsupported retrieval_mode: {value}") from exc


@dataclass
class DiagnosticQuery:
    raw_text: str
    sanitised_text: str
    failure_category: str | None = None
    pipeline_stage: str | None = None
    technologies: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    exception_names: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    file_types: list[str] = field(default_factory=list)
    aws_services: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    stack_trace_fingerprint: str | None = None
    organisation_id: UUID | None = None
    project_id: UUID | None = None
    incident_id: UUID | None = None

    def signal_summary(self) -> dict[str, Any]:
        """Safe summary for persistence — never includes raw unmasked logs."""
        return {
            "failure_category": self.failure_category,
            "pipeline_stage": self.pipeline_stage,
            "technologies": list(self.technologies)[:12],
            "error_codes": list(self.error_codes)[:12],
            "exception_names": list(self.exception_names)[:12],
            "commands": list(self.commands)[:12],
            "resource_types": list(self.resource_types)[:12],
            "file_types": list(self.file_types)[:12],
            "aws_services": list(self.aws_services)[:12],
            "keyword_count": len(self.keywords),
            "has_stack_trace_fingerprint": bool(self.stack_trace_fingerprint),
            "sanitised_query_length": len(self.sanitised_text),
            "organisation_id": str(self.organisation_id) if self.organisation_id else None,
            "project_id": str(self.project_id) if self.project_id else None,
            "incident_id": str(self.incident_id) if self.incident_id else None,
        }


@dataclass
class HybridScoreBreakdown:
    semantic: float | None = None
    keyword: float | None = None
    category: float | None = None
    stage: float | None = None
    technology: float | None = None
    error_code: float | None = None
    stack_trace: float | None = None
    resource: float | None = None
    authority: float | None = None
    recency: float | None = None
    history_quality: float | None = None
    penalties: dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    weight_profile: str = "embedding_baseline_v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalCandidate:
    candidate_id: str
    source_type: RetrievalSourceType
    source_id: str
    chunk_id: str | None
    title: str | None
    content_excerpt: str
    metadata: dict[str, Any] = field(default_factory=dict)
    semantic_score: float | None = None
    keyword_score: float | None = None
    category_score: float | None = None
    stage_score: float | None = None
    technology_score: float | None = None
    error_code_score: float | None = None
    stack_trace_score: float | None = None
    resource_score: float | None = None
    authority_score: float | None = None
    recency_score: float | None = None
    history_quality_score: float | None = None
    hybrid_score: float | None = None
    score_breakdown: HybridScoreBreakdown | None = None
    match_reasons: list[str] = field(default_factory=list)

    def clamp_scores(self) -> None:
        for name in (
            "semantic_score",
            "keyword_score",
            "category_score",
            "stage_score",
            "technology_score",
            "error_code_score",
            "stack_trace_score",
            "resource_score",
            "authority_score",
            "recency_score",
            "history_quality_score",
            "hybrid_score",
        ):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, clamp01(float(value)))


@dataclass
class RetrievalResult:
    query: DiagnosticQuery
    retrieval_mode: RetrievalMode
    candidates_considered: int
    candidates_selected: list[RetrievalCandidate]
    duplicate_count: int
    filtered_count: int
    retrieval_latency_ms: int
    fallback_used: bool
    fallback_reason: str | None
    configuration_hash: str
    weight_profile: str
    historical_candidates_considered: int = 0
    historical_candidates_selected: int = 0

    def evaluation_metadata(self) -> dict[str, Any]:
        return {
            "retrieval_mode": self.retrieval_mode.value,
            "weight_profile": self.weight_profile,
            "configuration_hash": self.configuration_hash,
            "candidates_considered": self.candidates_considered,
            "results_selected": len(self.candidates_selected),
            "duplicate_count": self.duplicate_count,
            "filtered_count": self.filtered_count,
            "historical_candidate_count": self.historical_candidates_considered,
            "historical_selected_count": self.historical_candidates_selected,
            "retrieval_latency_ms": self.retrieval_latency_ms,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "query_signal_summary": self.query.signal_summary(),
            "selected": [
                {
                    "candidate_id": c.candidate_id,
                    "source_type": c.source_type.value,
                    "source_id": c.source_id,
                    "chunk_id": c.chunk_id,
                    "title": c.title,
                    "hybrid_score": c.hybrid_score,
                    "semantic_score": c.semantic_score,
                    "match_reasons": list(c.match_reasons)[:8],
                    "score_breakdown": (c.score_breakdown.to_dict() if c.score_breakdown else None),
                }
                for c in self.candidates_selected
            ],
        }


@dataclass
class HistoricalIncidentDocument:
    incident_id: UUID
    organisation_id: UUID
    project_id: UUID | None
    title: str | None
    confirmed_category: str
    root_cause_summary: str
    resolution_summary: str
    technologies: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    pipeline_stage: str | None = None
    evidence_summary: list[str] = field(default_factory=list)
    resolved_at: datetime | None = None
    quality_score: float = 0.0
    content_hash: str = ""

    def indexed_text(self) -> str:
        parts = [
            self.confirmed_category.replace("_", " "),
            self.root_cause_summary,
            self.resolution_summary,
            " ".join(self.technologies),
            " ".join(self.error_codes),
            self.pipeline_stage or "",
            " ".join(self.evidence_summary[:5]),
        ]
        return " ".join(p for p in parts if p).strip()
