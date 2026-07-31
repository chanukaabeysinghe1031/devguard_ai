"""Structured outputs for Phase 6A.3 hierarchical classification."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.classification.enums import (
    AgreementLevel,
    ClassificationConflictType,
    ClassificationStatus,
    DisagreementRecommendedAction,
    OpenSetStatus,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class ClassificationCandidateDetail:
    category_code: str
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    score: float = 0.0
    source_classifier: str = "unknown"
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    rank: int = 1
    matched_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class StageClassifierResult:
    stage: str
    category_code: str | None = None
    confidence: float = 0.0
    top_candidates: list[ClassificationCandidateDetail] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    model_version: str | None = None
    representation_quality: float | None = None
    margin: float | None = None
    limitations: list[str] = field(default_factory=list)
    executed: bool = True
    skipped_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "category_code": self.category_code,
            "confidence": self.confidence,
            "top_candidates": [c.to_dict() for c in self.top_candidates],
            "matched_rules": list(self.matched_rules),
            "evidence_ids": list(self.evidence_ids),
            "model_version": self.model_version,
            "representation_quality": self.representation_quality,
            "margin": self.margin,
            "limitations": list(self.limitations),
            "executed": self.executed,
            "skipped_reason": self.skipped_reason,
            "raw": dict(self.raw),
        }


@dataclass(slots=True)
class OpenSetAssessment:
    status: OpenSetStatus = OpenSetStatus.UNCERTAIN
    unknown_score: float = 0.0
    maximum_known_score: float = 0.0
    top_two_margin: float = 0.0
    rule_coverage: float = 0.0
    representation_distance: float | None = None
    evidence_coverage: float = 0.0
    disagreement_level: str | None = None
    threshold_version: str = "open_set_v1"
    triggered_conditions: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class ClassificationDisagreementResult:
    agreement_level: AgreementLevel = AgreementLevel.NOT_APPLICABLE
    agreed_level_1: str | None = None
    agreed_level_2: str | None = None
    agreed_level_3: str | None = None
    conflicting_candidates: list[str] = field(default_factory=list)
    conflict_type: ClassificationConflictType = ClassificationConflictType.NONE
    evidence_conflict: bool = False
    classifier_conflict: bool = False
    category_distance: float = 0.0
    recommended_action: DisagreementRecommendedAction = DisagreementRecommendedAction.ACCEPT
    additional_evidence_needed: list[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agreement_level": self.agreement_level.value,
            "agreed_level_1": self.agreed_level_1,
            "agreed_level_2": self.agreed_level_2,
            "agreed_level_3": self.agreed_level_3,
            "conflicting_candidates": list(self.conflicting_candidates),
            "conflict_type": self.conflict_type.value,
            "evidence_conflict": self.evidence_conflict,
            "classifier_conflict": self.classifier_conflict,
            "category_distance": self.category_distance,
            "recommended_action": self.recommended_action.value,
            "additional_evidence_needed": list(self.additional_evidence_needed),
            "confidence_penalty": self.confidence_penalty,
            "explanation": self.explanation,
        }


@dataclass(slots=True)
class ClassificationConfidenceComponent:
    component_name: str
    raw_value: float
    normalized_value: float
    weight: float
    contribution: float
    source: str
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ClassificationConfidenceBreakdown:
    components: list[ClassificationConfidenceComponent] = field(default_factory=list)
    final_confidence: float = 0.0
    version: str = "classification_confidence_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "final_confidence": self.final_confidence,
            "version": self.version,
        }


@dataclass(slots=True)
class HierarchicalClassificationResult:
    analysis_id: str
    organization_id: str | None = None
    project_id: str | None = None
    incident_id: str | None = None
    final_legacy_category_code: str | None = None
    level_1_code: str | None = None
    level_2_code: str | None = None
    level_3_code: str | None = None
    classification_status: ClassificationStatus = ClassificationStatus.DISABLED
    top_candidates: list[ClassificationCandidateDetail] = field(default_factory=list)
    rule_result: StageClassifierResult | None = None
    learned_result: StageClassifierResult | None = None
    llm_result: StageClassifierResult | None = None
    open_set_result: OpenSetAssessment | None = None
    disagreement_result: ClassificationDisagreementResult | None = None
    confidence_breakdown: ClassificationConfidenceBreakdown | None = None
    evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    final_confidence: float = 0.0
    model_versions: dict[str, str] = field(default_factory=dict)
    mapping_version: str = "v1"
    duration_ms: int | None = None
    warnings: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
    evaluation_export: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "incident_id": self.incident_id,
            "final_legacy_category_code": self.final_legacy_category_code,
            "level_1_code": self.level_1_code,
            "level_2_code": self.level_2_code,
            "level_3_code": self.level_3_code,
            "classification_status": self.classification_status.value,
            "top_candidates": [c.to_dict() for c in self.top_candidates],
            "rule_result": self.rule_result.to_dict() if self.rule_result else None,
            "learned_result": self.learned_result.to_dict() if self.learned_result else None,
            "llm_result": self.llm_result.to_dict() if self.llm_result else None,
            "open_set_result": self.open_set_result.to_dict() if self.open_set_result else None,
            "disagreement_result": (
                self.disagreement_result.to_dict() if self.disagreement_result else None
            ),
            "confidence_breakdown": (
                self.confidence_breakdown.to_dict() if self.confidence_breakdown else None
            ),
            "evidence_ids": list(self.evidence_ids),
            "missing_evidence": list(self.missing_evidence),
            "final_confidence": self.final_confidence,
            "model_versions": dict(self.model_versions),
            "mapping_version": self.mapping_version,
            "duration_ms": self.duration_ms,
            "warnings": list(self.warnings),
            "created_at": self.created_at.isoformat(),
            "evaluation_export": dict(self.evaluation_export),
        }
