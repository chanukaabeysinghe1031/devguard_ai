"""Shared helpers and input bundle for Phase 6A.7 final diagnosis."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


@dataclass(slots=True)
class HypothesisSnapshot:
    hypothesis_id: str
    ranking_score: float = 0.0
    support_score: float = 0.0
    sufficiency_score: float = 0.0
    contradiction_penalty: float = 0.0
    temporal_confidence: float = 0.0
    graph_consistency: float = 0.0
    title: str = ""
    category_code: str = ""
    summary: str = ""
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RemediationCandidateSnapshot:
    candidate_id: str
    hypothesis_id: str | None = None
    risk_level: str = "UNKNOWN"
    risk_score: float = 0.0
    priority_status: str = ""
    priority_score: float = 0.0
    consensus_status: str | None = None
    constraint_status: str | None = None
    title: str = ""
    summary: str = ""
    artifact_type: str = ""
    verifier_results: list[dict[str, Any]] = field(default_factory=list)
    required_verifiers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FinalDiagnosisInputs:
    """Deterministic input bundle — constructed by tests or orchestrator wiring."""

    analysis_id: str
    organization_id: str
    incident_id: str | None = None
    project_id: str | None = None
    hypotheses: list[HypothesisSnapshot] = field(default_factory=list)
    candidates: list[RemediationCandidateSnapshot] = field(default_factory=list)
    open_set_status: str | None = None
    classifier_agreement: float = 0.5
    open_set_confidence: float = 0.5
    graph_completeness: float = 0.5
    artifacts_missing: list[str] = field(default_factory=list)
    what_failed: str = ""
    category_code: str | None = None
    top_hypothesis_margin: float | None = None
    flags: dict[str, bool] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    max_explanation_items: int = 10
