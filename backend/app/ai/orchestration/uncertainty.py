"""Uncertainty estimation — not a simple inverse of confidence."""

from __future__ import annotations

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.models import (
    ConfidenceAssessment,
    EvidenceQualityAssessment,
    RetrievalQualityAssessment,
    UncertaintyAssessment,
    UncertaintyLevel,
    clamp01,
)


class UncertaintyEstimator:
    def evaluate_baseline(
        self,
        context: AnalysisContext,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
    ) -> UncertaintyAssessment:
        return self._evaluate(
            context,
            confidence=confidence,
            evidence_quality=evidence_quality,
            retrieval_quality=None,
            agreement_status=None,
            unsupported_claims=0,
        )

    def evaluate_final(
        self,
        context: AnalysisContext,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        retrieval_quality: RetrievalQualityAssessment | None,
        agreement_status: str | None,
        unsupported_claims: int,
    ) -> UncertaintyAssessment:
        return self._evaluate(
            context,
            confidence=confidence,
            evidence_quality=evidence_quality,
            retrieval_quality=retrieval_quality,
            agreement_status=agreement_status,
            unsupported_claims=unsupported_claims,
        )

    def _evaluate(
        self,
        context: AnalysisContext,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        retrieval_quality: RetrievalQualityAssessment | None,
        agreement_status: str | None,
        unsupported_claims: int,
    ) -> UncertaintyAssessment:
        reasons: list[str] = []
        top = context.classifications[0] if context.classifications else None
        second = context.classifications[1] if len(context.classifications) > 1 else None
        ambiguity = 0.0
        conflicting: list[str] = []
        if top and second:
            ambiguity = clamp01(1.0 - max(0.0, float(top.confidence) - float(second.confidence)))
            if ambiguity >= 0.7:
                conflicting = [top.category_code, second.category_code]
                reasons.append("Close category scores increase ambiguity.")

        score = 0.35
        score += 0.25 * ambiguity
        score += 0.20 * (1.0 - evidence_quality.evidence_quality_score)
        score += 0.10 * (1.0 - confidence.calibrated_confidence)

        line_count = int((context.signals or {}).get("line_count") or 0)
        completeness = 1.0 if context.files and line_count >= 3 else 0.5 if context.files else 0.0
        score += 0.15 * (1.0 - completeness)
        if completeness < 0.9:
            reasons.append("Incomplete input increases uncertainty.")

        if top and top.category_code == "unknown_failure":
            score += 0.15
            reasons.append("unknown_failure increases uncertainty.")

        if evidence_quality.consistency_score < 0.6:
            score += 0.10
            reasons.append("Conflicting evidence increases uncertainty.")

        if retrieval_quality and retrieval_quality.retrieval_executed:
            rq = retrieval_quality.retrieval_quality_score or 0.0
            if rq < 0.55:
                score += 0.12
                reasons.append("Weak retrieval quality increases uncertainty.")
            else:
                score -= 0.08
                reasons.append("Strong retrieval support reduces uncertainty.")

        if agreement_status == "disagree":
            score += 0.15
            reasons.append("Deterministic/reasoner disagreement increases uncertainty.")
        elif agreement_status == "agree":
            score -= 0.08
            reasons.append("Deterministic/reasoner agreement reduces uncertainty.")

        if unsupported_claims > 0:
            score += min(0.20, 0.05 * unsupported_claims)
            reasons.append("Unsupported claims increase uncertainty.")

        if confidence.supporting_signal_count >= 3 and evidence_quality.direct_signature_count:
            score -= 0.08
            reasons.append("Strong signatures reduce uncertainty.")

        uncertainty = clamp01(score)
        # Intentionally not 1 - confidence.
        level = (
            UncertaintyLevel.HIGH
            if uncertainty >= 0.70
            else UncertaintyLevel.MEDIUM
            if uncertainty >= 0.40
            else UncertaintyLevel.LOW
        )
        return UncertaintyAssessment(
            uncertainty_score=round(uncertainty, 4),
            uncertainty_level=level,
            ambiguity_score=round(ambiguity, 4),
            input_completeness=round(completeness, 4),
            evidence_coverage=round(evidence_quality.coverage_score, 4),
            conflicting_categories=conflicting,
            reasons=reasons or ["Baseline uncertainty computed."],
        )
