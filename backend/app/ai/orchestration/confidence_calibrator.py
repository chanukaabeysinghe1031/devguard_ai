"""Heuristic rule-based confidence calibration (not statistical probability)."""

from __future__ import annotations

from typing import Protocol

from app.ai.orchestration.analysis_context import AnalysisContext
from app.ai.orchestration.models import (
    ConfidenceAssessment,
    ConfidenceBand,
    clamp01,
)


class ConfidenceCalibrator(Protocol):
    def calibrate(self, context: AnalysisContext) -> ConfidenceAssessment: ...


class RuleBasedConfidenceCalibrator:
    """Deterministic heuristic calibrator.

    Explicitly heuristic — not isotonic/Platt/statistical calibration.
    """

    METHOD = "rule_based_heuristic_v1"

    def calibrate(self, context: AnalysisContext) -> ConfidenceAssessment:
        top = context.classifications[0] if context.classifications else None
        second = context.classifications[1] if len(context.classifications) > 1 else None
        raw = clamp01(float(top.confidence) if top else 0.0)
        margin = None
        if top is not None and second is not None:
            margin = clamp01(float(top.confidence) - float(second.confidence))

        supporting = 0
        conflicting = 0
        reasons: list[str] = []
        score = raw

        matched_rules = list(top.matched_rules) if top else []
        strong_rules = [r for r in matched_rules if not str(r).startswith("keyword:")]
        weak_rules = [r for r in matched_rules if str(r).startswith("keyword:")]
        if strong_rules:
            supporting += len(strong_rules)
            score += min(0.08, 0.03 * len(strong_rules))
            reasons.append(f"Strong signature matches: {len(strong_rules)}.")
        if weak_rules and not strong_rules:
            conflicting += 1
            score -= 0.08
            reasons.append("Only weak keyword matches; confidence reduced.")

        evidence = context.evidence
        unique_files = {e.uploaded_file_id for e in evidence if e.uploaded_file_id}
        if evidence:
            supporting += min(3, len(evidence))
            score += min(0.06, 0.02 * len(unique_files))
            reasons.append(f"Evidence items={len(evidence)}, unique_files={len(unique_files)}.")
        else:
            conflicting += 1
            score -= 0.15
            reasons.append("No evidence extracted; confidence reduced.")

        if top and top.category_code == "unknown_failure":
            conflicting += 1
            score -= 0.20
            reasons.append("unknown_failure category lowers confidence.")

        if margin is not None and margin < 0.08:
            conflicting += 1
            score -= 0.10
            reasons.append("Small category margin increases uncertainty.")
        elif margin is not None and margin >= 0.20:
            supporting += 1
            score += 0.04
            reasons.append("Clear category margin supports confidence.")

        line_count = int((context.signals or {}).get("line_count") or 0)
        if not context.files or line_count < 2:
            conflicting += 1
            score -= 0.12
            reasons.append("Incomplete input lowers confidence.")
        else:
            supporting += 1

        excerpts = [e.normalized_excerpt[:120] for e in evidence]
        if excerpts and len(excerpts) != len(set(excerpts)):
            conflicting += 1
            score -= 0.05
            reasons.append("Duplicate evidence ignored for confidence inflation.")

        calibrated = clamp01(score)
        return ConfidenceAssessment(
            raw_confidence=round(raw, 4),
            calibrated_confidence=round(calibrated, 4),
            confidence_band=_band(calibrated),
            calibration_method=self.METHOD,
            supporting_signal_count=supporting,
            conflicting_signal_count=conflicting,
            category_margin=round(margin, 4) if margin is not None else None,
            reasons=reasons,
        )


def _band(score: float) -> ConfidenceBand:
    if score >= 0.85:
        return ConfidenceBand.HIGH
    if score >= 0.60:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW
