"""Deterministic final diagnosis confidence decomposition (heuristic, not calibrated)."""

from __future__ import annotations

from typing import Any

from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    clamp01,
)
from app.domain.final_diagnosis.enums import FinalConfidenceBand, VerifierSupportLevel
from app.domain.final_diagnosis.models import (
    FinalConfidenceBreakdown,
    VerifierAggregationResult,
)

_DEFAULT_WEIGHTS: dict[str, float] = {
    "hypothesis_ranking": 0.18,
    "evidence_sufficiency": 0.14,
    "support_score": 0.10,
    "temporal_support": 0.06,
    "graph_support": 0.06,
    "classifier_agreement": 0.08,
    "verifier_support": 0.16,
    "constraint_compliance": 0.06,
    "top_hypothesis_margin": 0.06,
    "contradiction_penalty": 0.14,
    "open_set_penalty": 0.10,
    "missing_artifact_penalty": 0.08,
    "remediation_risk_penalty": 0.10,
    "tie_penalty": 0.08,
}

_VERIFIER_SCORE = {
    VerifierSupportLevel.STRONG: 1.0,
    VerifierSupportLevel.MODERATE: 0.7,
    VerifierSupportLevel.WEAK: 0.4,
    VerifierSupportLevel.NONE: 0.0,
    VerifierSupportLevel.UNAVAILABLE: 0.15,
}


class FinalDiagnosisConfidenceCalculator:
    """Configuration-driven heuristic confidence. Not calibrated probability."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = dict(_DEFAULT_WEIGHTS)
        if weights:
            self._weights.update(weights)

    def calculate(
        self,
        inputs: FinalDiagnosisInputs,
        hypothesis: HypothesisSnapshot | None,
        verifier: VerifierAggregationResult,
        *,
        risk_score: float = 0.0,
        constraint_compliant: bool = True,
        margin: float | None = None,
    ) -> FinalConfidenceBreakdown:
        hyp = hypothesis or HypothesisSnapshot(hypothesis_id="none")
        margin_v = float(margin if margin is not None else (inputs.top_hypothesis_margin or 0.0))
        min_margin = float(inputs.thresholds.get("min_top_hypothesis_margin", 0.08))

        verifier_score = _VERIFIER_SCORE.get(verifier.support_level, 0.0)
        open_set = (inputs.open_set_status or "").upper()
        open_set_penalty = 1.0 if open_set in {"UNKNOWN", "OPEN", "NOVEL"} else 0.0
        if open_set_penalty == 0.0:
            open_set_penalty = clamp01(1.0 - float(inputs.open_set_confidence))

        missing_penalty = clamp01(len(inputs.artifacts_missing) / 3.0)
        risk_penalty = clamp01(float(risk_score))
        tie_penalty = 1.0 if margin_v < min_margin else 0.0
        constraint_score = 1.0 if constraint_compliant else 0.25

        components: dict[str, float] = {
            "hypothesis_ranking": clamp01(hyp.ranking_score),
            "evidence_sufficiency": clamp01(hyp.sufficiency_score),
            "support_score": clamp01(hyp.support_score),
            "temporal_support": clamp01(hyp.temporal_confidence),
            "graph_support": clamp01(
                hyp.graph_consistency if hyp.graph_consistency else inputs.graph_completeness
            ),
            "classifier_agreement": clamp01(inputs.classifier_agreement),
            "verifier_support": clamp01(verifier_score),
            "constraint_compliance": constraint_score,
            "top_hypothesis_margin": clamp01(margin_v / max(min_margin * 2.0, 1e-6)),
            "contradiction_penalty": clamp01(hyp.contradiction_penalty),
            "open_set_penalty": clamp01(open_set_penalty),
            "missing_artifact_penalty": missing_penalty,
            "remediation_risk_penalty": risk_penalty,
            "tie_penalty": tie_penalty,
        }

        positive_keys = (
            "hypothesis_ranking",
            "evidence_sufficiency",
            "support_score",
            "temporal_support",
            "graph_support",
            "classifier_agreement",
            "verifier_support",
            "constraint_compliance",
            "top_hypothesis_margin",
        )
        negative_keys = (
            "contradiction_penalty",
            "open_set_penalty",
            "missing_artifact_penalty",
            "remediation_risk_penalty",
            "tie_penalty",
        )

        positive = sum(self._weights[k] * components[k] for k in positive_keys)
        negative = sum(self._weights[k] * components[k] for k in negative_keys)
        # Normalize by total positive weight so score stays in ~[0,1]
        pos_weight = sum(self._weights[k] for k in positive_keys) or 1.0
        neg_weight = sum(self._weights[k] for k in negative_keys) or 1.0
        positive_n = positive / pos_weight
        negative_n = negative / neg_weight
        final = clamp01(positive_n - 0.55 * negative_n)

        band = self._band(final, inputs.thresholds)
        return FinalConfidenceBreakdown(
            final_confidence=round(final, 6),
            confidence_band=band,
            positive_score=round(positive_n, 6),
            negative_score=round(negative_n, 6),
            components={k: round(v, 6) for k, v in components.items()},
            weights=dict(self._weights),
        )

    @staticmethod
    def _band(score: float, thresholds: dict[str, Any]) -> FinalConfidenceBand:
        min_score = float(thresholds.get("min_final_diagnosis_score", 0.70))
        if score >= max(min_score, 0.85):
            return FinalConfidenceBand.HIGH
        if score >= min_score:
            return FinalConfidenceBand.MEDIUM
        if score >= 0.40:
            return FinalConfidenceBand.LOW
        return FinalConfidenceBand.INSUFFICIENT
