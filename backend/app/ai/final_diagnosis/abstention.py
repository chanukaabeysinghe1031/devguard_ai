"""Diagnosis abstention engine — intentional safe behavior, not an error."""

from __future__ import annotations

from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
    as_float,
)
from app.domain.final_diagnosis.enums import AbstentionReasonCode, VerifierSupportLevel
from app.domain.final_diagnosis.models import (
    AbstentionDecision,
    FinalConfidenceBreakdown,
    VerifierAggregationResult,
)

_CRITICAL_RISK = {"CRITICAL"}
_UNSAFE_PRIORITY = {"REJECTED_CANDIDATE", "NO_SAFE_CANDIDATE", "HIGH_RISK_CANDIDATE"}


class DiagnosisAbstentionEngine:
    """Block final diagnosis when any abstention rule fires."""

    def evaluate(
        self,
        inputs: FinalDiagnosisInputs,
        hypothesis: HypothesisSnapshot | None,
        candidate: RemediationCandidateSnapshot | None,
        verifier: VerifierAggregationResult,
        confidence: FinalConfidenceBreakdown,
        *,
        margin: float,
    ) -> AbstentionDecision:
        reasons: list[AbstentionReasonCode] = []
        missing: list[str] = list(inputs.artifacts_missing)
        suggestions: list[str] = []
        thresholds = inputs.thresholds

        open_set = (inputs.open_set_status or "").upper()
        if open_set in {"UNKNOWN", "OPEN", "NOVEL"}:
            reasons.append(AbstentionReasonCode.OPEN_SET_UNKNOWN)
            suggestions.append("Collect additional artifacts to classify the novel failure mode.")

        if hypothesis is None or not hypothesis.hypothesis_id:
            reasons.append(AbstentionReasonCode.EVIDENCE_INSUFFICIENT)
            missing.append("eligible_hypothesis")

        min_suff = as_float(thresholds.get("min_final_evidence_sufficiency"), 0.60)
        if hypothesis is not None and hypothesis.sufficiency_score < min_suff:
            reasons.append(AbstentionReasonCode.EVIDENCE_INSUFFICIENT)
            suggestions.append("Provide missing workflow, policy, or configuration artifacts.")

        min_margin = as_float(thresholds.get("min_top_hypothesis_margin"), 0.08)
        if margin < min_margin and len(inputs.hypotheses) >= 2:
            reasons.append(AbstentionReasonCode.HYPOTHESES_TIED)
            suggestions.append("Gather discriminating evidence between top hypotheses.")

        max_contra = as_float(thresholds.get("max_final_contradiction_penalty"), 0.40)
        if hypothesis is not None and hypothesis.contradiction_penalty > max_contra:
            reasons.append(AbstentionReasonCode.HIGH_CONTRADICTION)

        if verifier.blocking_failure or verifier.support_level == VerifierSupportLevel.NONE:
            reasons.append(AbstentionReasonCode.VERIFIER_FAILED)

        min_ver = as_float(thresholds.get("min_final_verifier_support"), 0.60)
        support_map = {
            VerifierSupportLevel.STRONG: 1.0,
            VerifierSupportLevel.MODERATE: 0.7,
            VerifierSupportLevel.WEAK: 0.4,
            VerifierSupportLevel.NONE: 0.0,
            VerifierSupportLevel.UNAVAILABLE: 0.0,
        }
        if support_map.get(verifier.support_level, 0.0) < min_ver:
            if verifier.support_level == VerifierSupportLevel.UNAVAILABLE:
                reasons.append(AbstentionReasonCode.VERIFIER_UNAVAILABLE)
            elif AbstentionReasonCode.VERIFIER_FAILED not in reasons:
                if verifier.unavailable_count and not verifier.failed_count:
                    reasons.append(AbstentionReasonCode.VERIFIER_UNAVAILABLE)
                elif verifier.failed_count:
                    reasons.append(AbstentionReasonCode.VERIFIER_FAILED)

        # High-risk change with unavailable *required* tools → abstain.
        risk = (candidate.risk_level if candidate else "UNKNOWN").upper()
        if (
            risk in {"HIGH", "CRITICAL"}
            and verifier.unavailable_tools
            and AbstentionReasonCode.VERIFIER_UNAVAILABLE not in reasons
        ):
            reasons.append(AbstentionReasonCode.VERIFIER_UNAVAILABLE)

        if candidate is None:
            reasons.append(AbstentionReasonCode.NO_SAFE_REMEDIATION)
        else:
            priority = (candidate.priority_status or "").upper()
            if priority in _UNSAFE_PRIORITY or priority == "NO_SAFE_CANDIDATE":
                reasons.append(AbstentionReasonCode.NO_SAFE_REMEDIATION)
            if risk in _CRITICAL_RISK:
                reasons.append(AbstentionReasonCode.HIGH_RISK_REMEDIATION)

        if inputs.graph_completeness < 0.25:
            reasons.append(AbstentionReasonCode.GRAPH_INCOMPLETE)
            missing.append("evidence_graph_coverage")

        if inputs.artifacts_missing:
            reasons.append(AbstentionReasonCode.ARTIFACTS_MISSING)

        if inputs.classifier_agreement < 0.35:
            reasons.append(AbstentionReasonCode.CLASSIFIER_DISAGREEMENT)

        min_conf = as_float(thresholds.get("min_final_diagnosis_score"), 0.70)
        if (
            confidence.final_confidence < min_conf
            and AbstentionReasonCode.EVIDENCE_INSUFFICIENT not in reasons
        ):
            reasons.append(AbstentionReasonCode.EVIDENCE_INSUFFICIENT)

        # Deduplicate while preserving order.
        deduped: list[AbstentionReasonCode] = []
        for code in reasons:
            if code not in deduped:
                deduped.append(code)

        should = bool(deduped)
        primary = deduped[0] if deduped else None
        explanation = (
            f"Abstaining due to {primary.value}."
            if primary
            else "No blocking abstention conditions."
        )
        return AbstentionDecision(
            should_abstain=should,
            primary_reason=primary,
            reason_codes=deduped,
            explanation=explanation,
            missing_evidence=missing,
            suggested_next_evidence=suggestions,
        )
