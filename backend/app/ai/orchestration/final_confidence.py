"""Final confidence recalibration after fusion and grounding."""

from __future__ import annotations

from app.ai.orchestration.models import (
    ConfidenceAssessment,
    EvidenceQualityAssessment,
    FinalConfidenceAssessment,
    FusionResult,
    RetrievalQualityAssessment,
    clamp01,
)


class FinalConfidenceRecalibrator:
    def recalibrate(
        self,
        *,
        confidence: ConfidenceAssessment,
        evidence_quality: EvidenceQualityAssessment,
        retrieval_quality: RetrievalQualityAssessment | None,
        fusion: FusionResult,
        grounding_valid: bool,
        reasoner_confidence: float | None,
        unsupported_claim_count: int,
        contradiction_count: int,
        fallback_used: bool,
    ) -> FinalConfidenceAssessment:
        baseline = confidence.calibrated_confidence
        score = baseline
        reasons: list[str] = []

        agreement = "none"
        if fusion.reasoner_category is None:
            agreement = "no_reasoner"
        elif fusion.baseline_category == fusion.reasoner_category:
            agreement = "agree"
        else:
            agreement = "disagree"

        grounding_coverage = 0.0
        if grounding_valid:
            grounding_coverage = 0.7
            if retrieval_quality and (retrieval_quality.retrieval_quality_score or 0) >= 0.55:
                grounding_coverage = 0.9
            score += 0.04
            reasons.append("Grounding validation passed.")
        else:
            reasons.append("Grounding weak or unavailable.")

        if agreement == "agree" and grounding_coverage >= 0.7:
            score += 0.05
            reasons.append("Agreement with grounding may increase confidence.")
        elif agreement == "disagree":
            score -= 0.08
            contradiction_count = max(contradiction_count, 1)
            reasons.append("Disagreement lowers confidence.")

        if unsupported_claim_count:
            score -= min(0.20, 0.05 * unsupported_claim_count)
            reasons.append("Unsupported claims lower confidence.")
        if contradiction_count:
            score -= min(0.15, 0.05 * contradiction_count)
            reasons.append("Contradictions lower confidence.")
        if fallback_used:
            score -= 0.06
            reasons.append("Fallback path lowers confidence.")

        score += 0.03 * evidence_quality.evidence_quality_score
        final = clamp01(score)
        # Do not trust LLM-supplied confidence as final.
        return FinalConfidenceAssessment(
            baseline_confidence=round(baseline, 4),
            reasoner_confidence=(
                round(clamp01(reasoner_confidence), 4) if reasoner_confidence is not None else None
            ),
            final_confidence=round(final, 4),
            confidence_delta=round(final - baseline, 4),
            agreement_status=agreement,
            grounding_coverage=round(grounding_coverage, 4),
            unsupported_claim_count=unsupported_claim_count,
            contradiction_count=contradiction_count,
            recalibration_reasons=reasons,
        )
