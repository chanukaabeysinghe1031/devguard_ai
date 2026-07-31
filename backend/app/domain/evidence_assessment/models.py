"""Domain contracts for Phase 6A.5 Part 3 evidence assessment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.evidence_assessment.enums import (
    CandidateSelectionStatus,
    EvidenceAssessmentType,
    EvidenceSufficiencyLevel,
)

EVIDENCE_ASSESSMENT_VERSION = "evidence_assessment_v1"
EVIDENCE_SUFFICIENCY_VERSION = "evidence_sufficiency_v1"
CONTRADICTION_ANALYSIS_VERSION = "contradiction_analysis_v1"
SUPPORT_ANALYSIS_VERSION = "support_analysis_v1"
HYPOTHESIS_RANKING_VERSION = "hypothesis_ranking_v1"
CANDIDATE_SELECTION_VERSION = "candidate_selection_v1"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class EvidenceAssessment:
    item_id: str
    hypothesis_id: str
    assessment_type: EvidenceAssessmentType
    confidence: float = 0.0
    relevance_score: float = 0.0
    authority_score: float = 0.0
    exact_identifier_overlap: float = 0.0
    source_type: str = ""
    relation_candidate: str = ""
    validation_status: str | None = None
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    assessor_version: str = EVIDENCE_ASSESSMENT_VERSION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "hypothesis_id": self.hypothesis_id,
            "assessment_type": self.assessment_type.value,
            "confidence": self.confidence,
            "relevance_score": self.relevance_score,
            "authority_score": self.authority_score,
            "exact_identifier_overlap": self.exact_identifier_overlap,
            "source_type": self.source_type,
            "relation_candidate": self.relation_candidate,
            "validation_status": self.validation_status,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "assessor_version": self.assessor_version,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class HypothesisSupportAssessment:
    hypothesis_id: str
    support_score: float = 0.0
    support_item_count: int = 0
    support_candidate_ids: list[str] = field(default_factory=list)
    component_scores: dict[str, float] = field(default_factory=dict)
    active_weights: dict[str, float] = field(default_factory=dict)
    contribution_by_component: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "support_score_is_not_root_cause_confidence",
            "support_candidates_are_not_causal_confirmation",
        ]
    )
    analyzer_version: str = SUPPORT_ANALYSIS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "support_score": self.support_score,
            "support_item_count": self.support_item_count,
            "support_candidate_ids": list(self.support_candidate_ids),
            "component_scores": dict(self.component_scores),
            "active_weights": dict(self.active_weights),
            "contribution_by_component": dict(self.contribution_by_component),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "analyzer_version": self.analyzer_version,
        }


@dataclass(slots=True)
class HypothesisContradictionAssessment:
    hypothesis_id: str
    contradiction_penalty: float = 0.0
    contradiction_item_count: int = 0
    contradiction_candidate_ids: list[str] = field(default_factory=list)
    strongest_contradiction_score: float = 0.0
    component_scores: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "contradiction_candidates_are_not_disproof",
            "contradiction_penalty_is_not_falsification",
        ]
    )
    analyzer_version: str = CONTRADICTION_ANALYSIS_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "contradiction_penalty": self.contradiction_penalty,
            "contradiction_item_count": self.contradiction_item_count,
            "contradiction_candidate_ids": list(self.contradiction_candidate_ids),
            "strongest_contradiction_score": self.strongest_contradiction_score,
            "component_scores": dict(self.component_scores),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "analyzer_version": self.analyzer_version,
        }


@dataclass(slots=True)
class EvidenceSufficiencyAssessment:
    hypothesis_id: str
    level: EvidenceSufficiencyLevel = EvidenceSufficiencyLevel.INSUFFICIENT
    sufficiency_score: float = 0.0
    coverage_score: float = 0.0
    authority_score: float = 0.0
    diversity_score: float = 0.0
    artifact_completeness: float = 0.0
    temporal_completeness: float = 0.0
    graph_completeness: float = 0.0
    documentation_completeness: float = 0.0
    historical_completeness: float = 0.0
    component_scores: dict[str, float] = field(default_factory=dict)
    active_weights: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "sufficiency_is_not_verification",
            "insufficient_evidence_does_not_disprove_hypothesis",
        ]
    )
    assessor_version: str = EVIDENCE_SUFFICIENCY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "level": self.level.value,
            "sufficiency_score": self.sufficiency_score,
            "coverage_score": self.coverage_score,
            "authority_score": self.authority_score,
            "diversity_score": self.diversity_score,
            "artifact_completeness": self.artifact_completeness,
            "temporal_completeness": self.temporal_completeness,
            "graph_completeness": self.graph_completeness,
            "documentation_completeness": self.documentation_completeness,
            "historical_completeness": self.historical_completeness,
            "component_scores": dict(self.component_scores),
            "active_weights": dict(self.active_weights),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "assessor_version": self.assessor_version,
        }


@dataclass(slots=True)
class HypothesisRankingScore:
    """Deterministic ranking score — not root-cause confidence."""

    hypothesis_id: str
    hypothesis_key: str = ""
    ranking_score: float = 0.0
    rank: int = 0
    component_scores: dict[str, float] = field(default_factory=dict)
    active_weights: dict[str, float] = field(default_factory=dict)
    contribution_by_component: dict[str, float] = field(default_factory=dict)
    support_score: float = 0.0
    contradiction_penalty: float = 0.0
    sufficiency_score: float = 0.0
    generation_prior_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "ranking_score_is_not_root_cause_confidence",
            "highest_ranked_is_not_confirmed_root_cause",
        ]
    )
    ranker_version: str = HYPOTHESIS_RANKING_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_key": self.hypothesis_key,
            "ranking_score": self.ranking_score,
            "rank": self.rank,
            "component_scores": dict(self.component_scores),
            "active_weights": dict(self.active_weights),
            "contribution_by_component": dict(self.contribution_by_component),
            "support_score": self.support_score,
            "contradiction_penalty": self.contradiction_penalty,
            "sufficiency_score": self.sufficiency_score,
            "generation_prior_score": self.generation_prior_score,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "ranker_version": self.ranker_version,
        }


@dataclass(slots=True)
class HypothesisRankingResult:
    analysis_id: str
    organization_id: str
    scores: list[HypothesisRankingScore] = field(default_factory=list)
    tie_epsilon: float = 0.02
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "ranking_score_is_not_root_cause_confidence",
            "candidates_only",
        ]
    )
    ranker_version: str = HYPOTHESIS_RANKING_VERSION
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "organization_id": self.organization_id,
            "scores": [s.to_dict() for s in self.scores],
            "tie_epsilon": self.tie_epsilon,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "ranker_version": self.ranker_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class HypothesisCandidateSelectionResult:
    analysis_id: str
    organization_id: str
    status: CandidateSelectionStatus = CandidateSelectionStatus.UNKNOWN
    top_hypothesis_id: str | None = None
    top_hypothesis_key: str | None = None
    top_ranking_score: float | None = None
    selected_hypothesis_ids: list[str] = field(default_factory=list)
    selected_hypothesis_keys: list[str] = field(default_factory=list)
    max_candidates: int = 5
    min_ranking_score_for_top: float = 0.40
    tie_epsilon: float = 0.02
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "selected_candidates_are_not_confirmed_root_causes",
            "candidate_selection_is_not_final_diagnosis",
        ]
    )
    selector_version: str = CANDIDATE_SELECTION_VERSION
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "organization_id": self.organization_id,
            "status": self.status.value,
            "top_hypothesis_id": self.top_hypothesis_id,
            "top_hypothesis_key": self.top_hypothesis_key,
            "top_ranking_score": self.top_ranking_score,
            "selected_hypothesis_ids": list(self.selected_hypothesis_ids),
            "selected_hypothesis_keys": list(self.selected_hypothesis_keys),
            "max_candidates": self.max_candidates,
            "min_ranking_score_for_top": self.min_ranking_score_for_top,
            "tie_epsilon": self.tie_epsilon,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "selector_version": self.selector_version,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class EvidenceAssessmentRun:
    """Groups per-analysis evidence assessments (candidates only)."""

    analysis_id: str
    organization_id: str
    retrieval_run_id: str | None = None
    status: str = "COMPLETE"
    hypothesis_assessments: dict[str, dict[str, Any]] = field(default_factory=dict)
    item_assessments: list[EvidenceAssessment] = field(default_factory=list)
    support_by_hypothesis: dict[str, HypothesisSupportAssessment] = field(default_factory=dict)
    contradiction_by_hypothesis: dict[str, HypothesisContradictionAssessment] = field(
        default_factory=dict
    )
    sufficiency_by_hypothesis: dict[str, EvidenceSufficiencyAssessment] = field(
        default_factory=dict
    )
    ranking: HypothesisRankingResult | None = None
    candidate_selection: HypothesisCandidateSelectionResult | None = None
    configuration_snapshot: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "evidence_assessment_produces_candidates_only",
            "no_causal_proof_language_in_outputs",
        ]
    )
    assessment_version: str = EVIDENCE_ASSESSMENT_VERSION
    created_at: datetime = field(default_factory=_utc_now)
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "organization_id": self.organization_id,
            "retrieval_run_id": self.retrieval_run_id,
            "status": self.status,
            "hypothesis_assessments": dict(self.hypothesis_assessments),
            "item_assessments": [a.to_dict() for a in self.item_assessments],
            "support_by_hypothesis": {
                k: v.to_dict() for k, v in self.support_by_hypothesis.items()
            },
            "contradiction_by_hypothesis": {
                k: v.to_dict() for k, v in self.contradiction_by_hypothesis.items()
            },
            "sufficiency_by_hypothesis": {
                k: v.to_dict() for k, v in self.sufficiency_by_hypothesis.items()
            },
            "ranking": self.ranking.to_dict() if self.ranking else None,
            "candidate_selection": (
                self.candidate_selection.to_dict() if self.candidate_selection else None
            ),
            "configuration_snapshot": dict(self.configuration_snapshot),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "assessment_version": self.assessment_version,
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.duration_ms,
        }

    def summary_dict(self) -> dict[str, Any]:
        """Compact summary for analysis context.options (no item dump)."""
        top = self.candidate_selection
        return {
            "status": self.status,
            "retrieval_run_id": self.retrieval_run_id,
            "assessment_version": self.assessment_version,
            "hypothesis_count": len(self.hypothesis_assessments),
            "item_assessment_count": len(self.item_assessments),
            "ranking_enabled": self.ranking is not None,
            "candidate_selection_status": top.status.value if top else None,
            "top_hypothesis_id": top.top_hypothesis_id if top else None,
            "top_ranking_score": top.top_ranking_score if top else None,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "duration_ms": self.duration_ms,
            "configuration_snapshot": dict(self.configuration_snapshot),
        }
