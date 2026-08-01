"""Final diagnosis decision engine — submission MVP."""

from __future__ import annotations

from app.ai.final_diagnosis.abstention import DiagnosisAbstentionEngine
from app.ai.final_diagnosis.aggregator import VerifierResultAggregator
from app.ai.final_diagnosis.confidence import FinalDiagnosisConfidenceCalculator
from app.ai.final_diagnosis.explanation import FinalDiagnosisExplanationBuilder
from app.ai.final_diagnosis.inputs import (
    FinalDiagnosisInputs,
    HypothesisSnapshot,
    RemediationCandidateSnapshot,
)
from app.domain.final_diagnosis.enums import (
    AbstentionReasonCode,
    FinalDiagnosisStatus,
    VerifierSupportLevel,
)
from app.domain.final_diagnosis.models import FinalDiagnosisDecision


class FinalDiagnosisDecisionEngine:
    """
    Fuse ranking + remediation + verifier aggregation into a final decision.

    Never applies remediation. Never mutates repositories or infrastructure.
    """

    def __init__(
        self,
        aggregator: VerifierResultAggregator | None = None,
        confidence: FinalDiagnosisConfidenceCalculator | None = None,
        abstention: DiagnosisAbstentionEngine | None = None,
        explanation: FinalDiagnosisExplanationBuilder | None = None,
    ) -> None:
        self._aggregator = aggregator or VerifierResultAggregator()
        self._confidence = confidence or FinalDiagnosisConfidenceCalculator()
        self._abstention = abstention or DiagnosisAbstentionEngine()
        self._explanation = explanation or FinalDiagnosisExplanationBuilder()

    def decide(self, inputs: FinalDiagnosisInputs) -> FinalDiagnosisDecision:
        try:
            return self._decide(inputs)
        except Exception as exc:  # noqa: BLE001
            return FinalDiagnosisDecision(
                analysis_id=inputs.analysis_id,
                organization_id=inputs.organization_id,
                incident_id=inputs.incident_id,
                project_id=inputs.project_id,
                status=FinalDiagnosisStatus.FAILED,
                warnings=[f"final_diagnosis_failed:{type(exc).__name__}"],
                abstention_reason_codes=[AbstentionReasonCode.INTERNAL_FAILURE.value],
                final_summary="Final diagnosis engine failed; baseline analysis unchanged.",
            )

    def _decide(self, inputs: FinalDiagnosisInputs) -> FinalDiagnosisDecision:
        if not inputs.flags.get("final_diagnosis_enabled", False):
            return FinalDiagnosisDecision(
                analysis_id=inputs.analysis_id,
                organization_id=inputs.organization_id,
                incident_id=inputs.incident_id,
                project_id=inputs.project_id,
                status=FinalDiagnosisStatus.DISABLED,
                final_summary="Final diagnosis disabled by feature flag.",
            )

        hyp = self._select_hypothesis(inputs)
        cand = self._select_candidate(inputs, hyp)
        verifier = self._aggregator.aggregate(
            cand,
            required_verifiers=list(cand.required_verifiers) if cand else None,
            consensus_status=cand.consensus_status if cand else None,
        )
        margin = self._margin(inputs)
        constraint_ok = True
        if cand and cand.constraint_status:
            constraint_ok = cand.constraint_status.upper() in {
                "STRUCTURALLY_COMPLIANT",
                "COMPLIANT_WITH_WARNINGS",
                "",
            }

        conf = self._confidence.calculate(
            inputs,
            hyp,
            verifier,
            risk_score=cand.risk_score if cand else 1.0,
            constraint_compliant=constraint_ok,
            margin=margin,
        )

        abstain_enabled = inputs.flags.get("diagnosis_abstention_enabled", True)
        if abstain_enabled:
            abstention = self._abstention.evaluate(
                inputs,
                hyp,
                cand,
                verifier,
                conf,
                margin=margin,
            )
        else:
            from app.domain.final_diagnosis.models import AbstentionDecision

            abstention = AbstentionDecision(
                should_abstain=False,
                explanation="Abstention engine disabled.",
            )

        status = self._map_status(inputs, hyp, cand, verifier, abstention, conf.final_confidence)

        explanation = None
        if inputs.flags.get("final_explanation_enabled", True):
            explanation = self._explanation.build(
                inputs,
                status,
                hyp,
                cand,
                verifier,
                abstention,
                max_items=inputs.max_explanation_items,
            )

        diagnosed = status in {
            FinalDiagnosisStatus.DIAGNOSED,
            FinalDiagnosisStatus.DIAGNOSED_WITH_WARNINGS,
        }

        title = None
        summary = None
        root = None
        category = inputs.category_code
        if diagnosed and hyp:
            title = hyp.title or f"Hypothesis {hyp.hypothesis_id}"
            summary = hyp.summary or title
            root = f"Most likely contributing cause (evidence-based only): {summary}"
            category = hyp.category_code or category
        elif status == FinalDiagnosisStatus.UNKNOWN:
            summary = "Open-set or unsupported failure; no taxonomy diagnosis forced."
        elif status == FinalDiagnosisStatus.CONFLICTED:
            summary = "Top hypotheses are too close or contradictory to select one."
        elif status == FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE:
            summary = "Insufficient evidence or verifier support for a final diagnosis."

        warnings: list[str] = []
        if status == FinalDiagnosisStatus.DIAGNOSED_WITH_WARNINGS:
            warnings.append("non_blocking_uncertainty_present")
        if verifier.warning_count:
            warnings.append("verifier_warnings_present")
        if verifier.unavailable_count:
            warnings.append("some_verifiers_unavailable")

        return FinalDiagnosisDecision(
            analysis_id=inputs.analysis_id,
            organization_id=inputs.organization_id,
            incident_id=inputs.incident_id,
            project_id=inputs.project_id,
            status=status,
            selected_hypothesis_id=(
                hyp.hypothesis_id
                if hyp
                and (
                    diagnosed
                    or status
                    in {
                        FinalDiagnosisStatus.CONFLICTED,
                        FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE,
                    }
                )
                else None
            ),
            selected_remediation_candidate_id=(cand.candidate_id if cand and diagnosed else None),
            final_category_code=category if diagnosed else None,
            final_title=title if diagnosed else None,
            final_summary=summary,
            root_cause_statement=root if diagnosed else None,
            confidence=conf.final_confidence
            if inputs.flags.get("final_confidence_enabled", True)
            else 0.0,
            confidence_band=conf.confidence_band,
            verifier_support=verifier.support_level,
            evidence_sufficiency=hyp.sufficiency_score if hyp else 0.0,
            contradiction_penalty=hyp.contradiction_penalty if hyp else 0.0,
            top_hypothesis_margin=margin,
            abstention_reason_codes=[c.value for c in abstention.reason_codes],
            missing_evidence=list(abstention.missing_evidence),
            warnings=warnings,
            explanation=explanation,
            confidence_breakdown=conf
            if inputs.flags.get("final_confidence_enabled", True)
            else None,
            abstention=abstention,
            verifier_aggregation=verifier,
            component_scores=dict(conf.components),
        )

    def _select_hypothesis(self, inputs: FinalDiagnosisInputs) -> HypothesisSnapshot | None:
        if not inputs.hypotheses:
            return None
        ordered = sorted(inputs.hypotheses, key=lambda h: (-h.ranking_score, h.hypothesis_id))
        return ordered[0]

    def _select_candidate(
        self,
        inputs: FinalDiagnosisInputs,
        hyp: HypothesisSnapshot | None,
    ) -> RemediationCandidateSnapshot | None:
        if not inputs.candidates:
            return None
        preferred_consensus = {"VERIFIED", "PARTIALLY_VERIFIED"}
        scored: list[tuple[float, RemediationCandidateSnapshot]] = []
        for c in inputs.candidates:
            if hyp and c.hypothesis_id and c.hypothesis_id != hyp.hypothesis_id:
                # Prefer matching hypothesis but allow fallbacks.
                hyp_match = 0.0
            else:
                hyp_match = 1.0
            consensus = (c.consensus_status or "").upper()
            c_score = 0.0
            if consensus in preferred_consensus:
                c_score += 0.5
            if consensus == "VERIFIED":
                c_score += 0.2
            risk = (c.risk_level or "").upper()
            if risk == "CRITICAL":
                c_score -= 1.0
            elif risk == "HIGH":
                c_score -= 0.3
            priority = (c.priority_status or "").upper()
            if priority in {"REJECTED_CANDIDATE", "NO_SAFE_CANDIDATE"}:
                c_score -= 1.0
            c_score += float(c.priority_score) * 0.2
            c_score += hyp_match
            scored.append((c_score, c))
        scored.sort(key=lambda t: (-t[0], t[1].candidate_id))
        return scored[0][1] if scored else None

    def _margin(self, inputs: FinalDiagnosisInputs) -> float:
        if inputs.top_hypothesis_margin is not None:
            return float(inputs.top_hypothesis_margin)
        if len(inputs.hypotheses) < 2:
            return 1.0
        ordered = sorted(inputs.hypotheses, key=lambda h: (-h.ranking_score, h.hypothesis_id))
        return max(0.0, ordered[0].ranking_score - ordered[1].ranking_score)

    def _map_status(
        self,
        inputs: FinalDiagnosisInputs,
        hyp: HypothesisSnapshot | None,
        cand: RemediationCandidateSnapshot | None,
        verifier,
        abstention,
        confidence: float,
    ) -> FinalDiagnosisStatus:
        open_set = (inputs.open_set_status or "").upper()
        if open_set in {"UNKNOWN", "OPEN", "NOVEL"}:
            return FinalDiagnosisStatus.UNKNOWN

        if AbstentionReasonCode.HYPOTHESES_TIED in abstention.reason_codes:
            return FinalDiagnosisStatus.CONFLICTED
        if AbstentionReasonCode.HIGH_CONTRADICTION in abstention.reason_codes:
            return FinalDiagnosisStatus.CONFLICTED
        if AbstentionReasonCode.CLASSIFIER_DISAGREEMENT in abstention.reason_codes and (
            AbstentionReasonCode.HYPOTHESES_TIED in abstention.reason_codes or hyp is None
        ):
            return FinalDiagnosisStatus.CONFLICTED

        if abstention.should_abstain:
            if AbstentionReasonCode.OPEN_SET_UNKNOWN in abstention.reason_codes:
                return FinalDiagnosisStatus.UNKNOWN
            return FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE

        # Diagnose path.
        if hyp is None or cand is None:
            return FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE

        strong_ok = verifier.support_level in {
            VerifierSupportLevel.STRONG,
            VerifierSupportLevel.MODERATE,
        }
        min_score = float(inputs.thresholds.get("min_final_diagnosis_score", 0.70))
        if (
            strong_ok
            and confidence >= min_score
            and verifier.support_level == VerifierSupportLevel.STRONG
            and verifier.warning_count == 0
            and verifier.unavailable_count == 0
        ):
            return FinalDiagnosisStatus.DIAGNOSED
        if strong_ok and confidence >= min_score:
            return FinalDiagnosisStatus.DIAGNOSED_WITH_WARNINGS
        return FinalDiagnosisStatus.INSUFFICIENT_EVIDENCE
