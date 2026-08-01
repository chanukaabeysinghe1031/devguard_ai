"""Phase 6A.6 Part 2 — side-effect analyser (static predictions only)."""

from __future__ import annotations

from app.domain.counterfactual_remediation.generation_enums import RiskLevel
from app.domain.counterfactual_remediation.generation_models import SideEffectAssessment
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


class RemediationSideEffectAnalyzer:
    def analyse(self, candidate: CounterfactualRemediationCandidate) -> SideEffectAssessment:
        predicted: list[str] = []
        unknown: list[str] = ["runtime_effects_unknown", "operational_correctness_unverified"]

        for change in candidate.changes or []:
            ctype = str(change.change_type).upper()
            if "PERMISSION" in ctype:
                predicted.append("identity_policy_evaluation_may_change")
            if "ROLE" in ctype:
                predicted.append("assumed_role_principal_may_change")
            if "DEPENDENCY" in ctype or "VERSION" in ctype:
                predicted.append("lockfile_or_resolve_graph_may_change")
            if change.source_path and change.source_path.endswith(
                ("package-lock.json", "yarn.lock", "poetry.lock")
            ):
                predicted.append("lock_file_side_effect")

        if not candidate.changes:
            unknown.append("no_structured_changes")

        severity = RiskLevel.LOW
        if any("lock_file" in p for p in predicted):
            severity = RiskLevel.MEDIUM
        if len(predicted) >= 3:
            severity = RiskLevel.MEDIUM

        return SideEffectAssessment(
            expected_intended_effects=list(candidate.expected_effects or [])[:20],
            potential_side_effects=predicted[:20],
            unknown_effects=unknown[:20],
            severity=severity,
        )
