"""Domain contracts for Phase 6A.7 final diagnosis submission MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.final_diagnosis.enums import (
    AbstentionReasonCode,
    FinalConfidenceBand,
    FinalDiagnosisStatus,
    VerifierSupportLevel,
)
from app.domain.final_diagnosis.versions import (
    ABSTENTION_ENGINE_VERSION,
    FINAL_CONFIDENCE_VERSION,
    FINAL_DIAGNOSIS_DECISION_VERSION,
    FINAL_EXPLANATION_VERSION,
    VERIFIER_AGGREGATION_VERSION,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _enum_val(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


@dataclass(slots=True)
class VerifierAggregationResult:
    candidate_id: str | None = None
    required_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    unavailable_count: int = 0
    warning_count: int = 0
    support_level: VerifierSupportLevel = VerifierSupportLevel.UNAVAILABLE
    blocking_failure: bool = False
    consensus_status: str | None = None
    summary: str = ""
    limitations: list[str] = field(
        default_factory=lambda: [
            "verifier_support_is_not_applied_remediation",
            "unavailable_never_counts_as_pass",
        ]
    )
    warnings: list[str] = field(default_factory=list)
    unavailable_tools: list[str] = field(default_factory=list)
    failed_tools: list[str] = field(default_factory=list)
    aggregator_version: str = VERIFIER_AGGREGATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "required_count": self.required_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "unavailable_count": self.unavailable_count,
            "warning_count": self.warning_count,
            "support_level": _enum_val(self.support_level),
            "blocking_failure": self.blocking_failure,
            "consensus_status": self.consensus_status,
            "summary": self.summary,
            "limitations": list(self.limitations),
            "warnings": list(self.warnings),
            "unavailable_tools": list(self.unavailable_tools),
            "failed_tools": list(self.failed_tools),
            "aggregator_version": self.aggregator_version,
        }


@dataclass(slots=True)
class FinalConfidenceBreakdown:
    final_confidence: float = 0.0
    confidence_band: FinalConfidenceBand = FinalConfidenceBand.INSUFFICIENT
    positive_score: float = 0.0
    negative_score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    weights: dict[str, float] = field(default_factory=dict)
    limitations: list[str] = field(
        default_factory=lambda: [
            "heuristic_score_not_calibrated_probability",
            "final_confidence_is_not_mathematical_proof",
        ]
    )
    calculator_version: str = FINAL_CONFIDENCE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_confidence": self.final_confidence,
            "confidence_band": _enum_val(self.confidence_band),
            "positive_score": self.positive_score,
            "negative_score": self.negative_score,
            "components": dict(self.components),
            "weights": dict(self.weights),
            "limitations": list(self.limitations),
            "calculator_version": self.calculator_version,
        }


@dataclass(slots=True)
class AbstentionDecision:
    should_abstain: bool = True
    primary_reason: AbstentionReasonCode | None = None
    reason_codes: list[AbstentionReasonCode] = field(default_factory=list)
    explanation: str = ""
    missing_evidence: list[str] = field(default_factory=list)
    suggested_next_evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "abstention_is_intentional_safe_behavior",
            "abstention_does_not_apply_remediation",
        ]
    )
    engine_version: str = ABSTENTION_ENGINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_abstain": self.should_abstain,
            "primary_reason": (
                _enum_val(self.primary_reason) if self.primary_reason is not None else None
            ),
            "reason_codes": [_enum_val(c) for c in self.reason_codes],
            "explanation": self.explanation,
            "missing_evidence": list(self.missing_evidence),
            "suggested_next_evidence": list(self.suggested_next_evidence),
            "limitations": list(self.limitations),
            "engine_version": self.engine_version,
        }


@dataclass(slots=True)
class FinalDiagnosisExplanation:
    sections: dict[str, str] = field(default_factory=dict)
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    verifier_summary: str = ""
    remediation_summary: str = ""
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "explanation_is_structured_summary_only",
            "no_hidden_chain_of_thought",
        ]
    )
    builder_version: str = FINAL_EXPLANATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": dict(self.sections),
            "supporting_evidence_ids": list(self.supporting_evidence_ids),
            "contradicting_evidence_ids": list(self.contradicting_evidence_ids),
            "missing_evidence": list(self.missing_evidence),
            "verifier_summary": self.verifier_summary,
            "remediation_summary": self.remediation_summary,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "builder_version": self.builder_version,
        }


@dataclass(slots=True)
class FinalDiagnosisDecision:
    analysis_id: str
    organization_id: str
    incident_id: str | None = None
    project_id: str | None = None
    status: FinalDiagnosisStatus = FinalDiagnosisStatus.DISABLED
    selected_hypothesis_id: str | None = None
    selected_remediation_candidate_id: str | None = None
    final_category_code: str | None = None
    final_title: str | None = None
    final_summary: str | None = None
    root_cause_statement: str | None = None
    confidence: float = 0.0
    confidence_band: FinalConfidenceBand = FinalConfidenceBand.INSUFFICIENT
    verifier_support: VerifierSupportLevel = VerifierSupportLevel.UNAVAILABLE
    evidence_sufficiency: float = 0.0
    contradiction_penalty: float = 0.0
    top_hypothesis_margin: float = 0.0
    abstention_reason_codes: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(
        default_factory=lambda: [
            "final_diagnosis_is_evidence_based_not_mathematical_proof",
            "verified_remediation_is_not_applied_remediation",
            "highest_ranked_hypothesis_is_not_proven_root_cause",
        ]
    )
    explanation: FinalDiagnosisExplanation | None = None
    confidence_breakdown: FinalConfidenceBreakdown | None = None
    abstention: AbstentionDecision | None = None
    verifier_aggregation: VerifierAggregationResult | None = None
    component_scores: dict[str, float] = field(default_factory=dict)
    decision_version: str = FINAL_DIAGNOSIS_DECISION_VERSION
    created_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "incident_id": self.incident_id,
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "status": _enum_val(self.status),
            "selected_hypothesis_id": self.selected_hypothesis_id,
            "selected_remediation_candidate_id": self.selected_remediation_candidate_id,
            "final_category_code": self.final_category_code,
            "final_title": self.final_title,
            "final_summary": self.final_summary,
            "root_cause_statement": self.root_cause_statement,
            "confidence": self.confidence,
            "confidence_band": _enum_val(self.confidence_band),
            "verifier_support": _enum_val(self.verifier_support),
            "evidence_sufficiency": self.evidence_sufficiency,
            "contradiction_penalty": self.contradiction_penalty,
            "top_hypothesis_margin": self.top_hypothesis_margin,
            "abstention_reason_codes": list(self.abstention_reason_codes),
            "missing_evidence": list(self.missing_evidence),
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "explanation": self.explanation.to_dict() if self.explanation else None,
            "confidence_breakdown": (
                self.confidence_breakdown.to_dict() if self.confidence_breakdown else None
            ),
            "abstention": self.abstention.to_dict() if self.abstention else None,
            "verifier_aggregation": (
                self.verifier_aggregation.to_dict() if self.verifier_aggregation else None
            ),
            "component_scores": dict(self.component_scores),
            "decision_version": self.decision_version,
            "created_at": self.created_at.isoformat(),
        }
