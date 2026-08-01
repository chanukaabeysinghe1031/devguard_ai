"""Deterministic hypothesis eligibility for Phase 6A.6 Part 1 counterfactual remediation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.counterfactual_remediation.enums import HypothesisEligibilityStatus
from app.domain.counterfactual_remediation.models import HypothesisEligibilityResult
from app.domain.evidence_assessment.enums import (
    CandidateSelectionStatus,
    EvidenceSufficiencyLevel,
)
from app.domain.hypotheses.enums import CriticDecision

# Heuristic threshold: at/above this contradiction penalty blocks eligibility.
_STRONG_CONTRADICTION_PENALTY = 0.70

_REJECTING_CRITIC = {
    CriticDecision.REJECT.value,
    CriticDecision.CONTRADICTED.value,
    "REJECTED",
}

_TOP_STATUSES = {
    CandidateSelectionStatus.TOP_CANDIDATE.value,
    CandidateSelectionStatus.TOP_N.value,
}

_TIE_STATUSES = {CandidateSelectionStatus.TIE.value}
_WEAK_STATUSES = {CandidateSelectionStatus.WEAK_EVIDENCE.value}
_UNKNOWN_SELECTION = {
    CandidateSelectionStatus.UNKNOWN.value,
    "",
    "NONE",
}
_OPEN_SET_UNKNOWN = {"UNKNOWN"}


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    text = str(value).strip()
    return text if text else None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "ok"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def _sufficiency_level(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return _as_str(value.get("level"))
    return _as_str(value)


def _normalize_inputs(
    inputs: Mapping[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if inputs is not None:
        merged.update(dict(inputs))
    # Explicit kwargs override mapping values (skip unset sentinels).
    for key, value in kwargs.items():
        if value is not None:
            merged[key] = value
    return merged


class CounterfactualHypothesisEligibilityEvaluator:
    """Deterministic eligibility rules (brief §37 / section 8). Candidates only."""

    def evaluate(
        self,
        inputs: Mapping[str, Any] | None = None,
        /,
        *,
        hypothesis_id: str | None = None,
        candidate_selection_status: Any = None,
        ranking_score: Any = None,
        evidence_sufficiency: Any = None,
        contradiction_penalty: Any = None,
        open_set_status: Any = None,
        critic_decision: Any = None,
        affected_artifact_available: bool | None = None,
        graph_path_ok: bool | None = None,
        constraint_sources_available: bool | None = None,
        allow_weak_evidence: bool | None = None,
        **extra: Any,
    ) -> HypothesisEligibilityResult:
        """Evaluate whether a hypothesis may enter counterfactual remediation planning.

        Accepts keyword arguments and/or a single mapping of the same keys.
        """
        merged = _normalize_inputs(
            inputs,
            {
                "hypothesis_id": hypothesis_id,
                "candidate_selection_status": candidate_selection_status,
                "ranking_score": ranking_score,
                "evidence_sufficiency": evidence_sufficiency,
                "contradiction_penalty": contradiction_penalty,
                "open_set_status": open_set_status,
                "critic_decision": critic_decision,
                "affected_artifact_available": affected_artifact_available,
                "graph_path_ok": graph_path_ok,
                "constraint_sources_available": constraint_sources_available,
                "allow_weak_evidence": allow_weak_evidence,
                **extra,
            },
        )

        selection = (
            _as_str(merged.get("candidate_selection_status"))
            or CandidateSelectionStatus.UNKNOWN.value
        ).upper()
        ranking = _as_float(merged.get("ranking_score"))
        sufficiency = (_sufficiency_level(merged.get("evidence_sufficiency")) or "").upper()
        contradiction = _as_float(merged.get("contradiction_penalty")) or 0.0
        open_set = (_as_str(merged.get("open_set_status")) or "").upper()
        critic = (_as_str(merged.get("critic_decision")) or "").upper()
        artifact_ok = _as_bool(merged.get("affected_artifact_available"), False)
        graph_ok = _as_bool(merged.get("graph_path_ok"), False)
        constraints_ok = _as_bool(merged.get("constraint_sources_available"), False)
        allow_weak = _as_bool(merged.get("allow_weak_evidence"), False)
        hyp_id = _as_str(merged.get("hypothesis_id"))

        snapshot = {
            "candidate_selection_status": selection,
            "ranking_score": ranking,
            "evidence_sufficiency": sufficiency or None,
            "contradiction_penalty": contradiction,
            "open_set_status": open_set or None,
            "critic_decision": critic or None,
            "affected_artifact_available": artifact_ok,
            "graph_path_ok": graph_ok,
            "constraint_sources_available": constraints_ok,
            "allow_weak_evidence": allow_weak,
        }

        reasons: list[str] = []
        warnings: list[str] = []
        blocking: list[str] = []
        missing: list[str] = []

        rejecting = {c.upper() for c in _REJECTING_CRITIC}
        if critic in rejecting:
            blocking.append(f"critic_decision={critic}")
            reasons.append("hypothesis_rejected_or_contradicted_by_critic")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INELIGIBLE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        if contradiction >= _STRONG_CONTRADICTION_PENALTY:
            blocking.append(f"contradiction_penalty>={_STRONG_CONTRADICTION_PENALTY}")
            reasons.append("strong_contradiction_blocks_remediation")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INELIGIBLE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        if open_set in _OPEN_SET_UNKNOWN and not artifact_ok:
            blocking.append("open_set_unknown_without_affected_artifact")
            reasons.append("unknown_cause_with_no_safe_generic_change")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.BLOCKED,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=["affected_artifact"],
                input_snapshot=snapshot,
            )

        if selection in {s.upper() for s in _UNKNOWN_SELECTION} and not artifact_ok:
            blocking.append("unknown_selection_without_affected_artifact")
            reasons.append("no_actionable_artifact_for_unknown_selection")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INELIGIBLE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=["affected_artifact"],
                input_snapshot=snapshot,
            )

        if selection in {s.upper() for s in _WEAK_STATUSES}:
            if not allow_weak:
                reasons.append("weak_evidence_not_allowed")
                blocking.append("WEAK_EVIDENCE_requires_allow_weak_evidence")
                return HypothesisEligibilityResult(
                    status=HypothesisEligibilityStatus.INELIGIBLE,
                    hypothesis_id=hyp_id,
                    reasons=reasons,
                    warnings=warnings,
                    blocking_reasons=blocking,
                    missing_prerequisites=missing,
                    input_snapshot=snapshot,
                )
            warnings.append("weak_evidence_allowed_for_tentative_planning")

        is_top = selection in {s.upper() for s in _TOP_STATUSES}
        is_tie = selection in {s.upper() for s in _TIE_STATUSES}
        is_weak_allowed = selection in {s.upper() for s in _WEAK_STATUSES} and allow_weak
        is_selected_family = is_top or is_tie or is_weak_allowed

        if not is_selected_family:
            if selection in {s.upper() for s in _UNKNOWN_SELECTION}:
                reasons.append("candidate_selection_status_unknown")
            else:
                reasons.append(f"unsupported_or_non_selected_status={selection}")
            if not artifact_ok:
                missing.append("affected_artifact")
                reasons.append("no_affected_artifact")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INELIGIBLE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        if not artifact_ok:
            missing.append("affected_artifact")
            reasons.append("likely_hypothesis_but_affected_artifact_missing")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INCOMPLETE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        if not constraints_ok:
            missing.append("constraint_sources")
            warnings.append("constraint_sources_unavailable")
            reasons.append("selected_hypothesis_missing_constraint_sources")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.INCOMPLETE,
                hypothesis_id=hyp_id,
                reasons=reasons,
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        if not graph_ok:
            warnings.append("graph_path_incomplete_or_unavailable")
            missing.append("graph_path")

        if sufficiency == EvidenceSufficiencyLevel.INSUFFICIENT.value:
            warnings.append("evidence_sufficiency_insufficient")
        elif sufficiency == EvidenceSufficiencyLevel.LOW.value:
            warnings.append("evidence_sufficiency_low")

        if critic == CriticDecision.ACCEPT_WITH_WARNINGS.value:
            warnings.append("critic_accept_with_warnings")
        elif critic == CriticDecision.INCOMPLETE.value:
            warnings.append("critic_marked_incomplete")

        if ranking is not None and ranking < 0.0:
            warnings.append("negative_ranking_score")

        if is_tie or is_weak_allowed or warnings or missing:
            if is_tie:
                reasons.append("tie_candidate_eligible_with_warnings")
            elif is_weak_allowed:
                reasons.append("weak_evidence_eligible_with_warnings")
            elif is_top:
                reasons.append("top_candidate_eligible_with_warnings")
            return HypothesisEligibilityResult(
                status=HypothesisEligibilityStatus.ELIGIBLE_WITH_WARNINGS,
                hypothesis_id=hyp_id,
                reasons=reasons or ["eligible_with_warnings"],
                warnings=warnings,
                blocking_reasons=blocking,
                missing_prerequisites=missing,
                input_snapshot=snapshot,
            )

        reasons.append("top_or_top_n_candidate_eligible")
        reasons.append("affected_artifact_available")
        reasons.append("no_blocking_contradiction")
        return HypothesisEligibilityResult(
            status=HypothesisEligibilityStatus.ELIGIBLE,
            hypothesis_id=hyp_id,
            reasons=reasons,
            warnings=warnings,
            blocking_reasons=blocking,
            missing_prerequisites=missing,
            input_snapshot=snapshot,
        )
