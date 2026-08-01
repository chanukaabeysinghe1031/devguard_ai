"""Phase 6A.6 Part 2 — static risk analyser (heuristic; not verification)."""

from __future__ import annotations

from app.ai.counterfactual_remediation.generation._helpers import contains_wildcard
from app.domain.counterfactual_remediation.enums import ConstraintSeverity, RemediationRiskType
from app.domain.counterfactual_remediation.generation_enums import RiskLevel
from app.domain.counterfactual_remediation.generation_models import RemediationRiskAssessment
from app.domain.counterfactual_remediation.models import (
    CounterfactualRemediationCandidate,
    RemediationRiskSignal,
)


class RemediationRiskAnalyzer:
    """Decompose static risk from candidate patches/changes."""

    def analyse(
        self,
        candidate: CounterfactualRemediationCandidate,
        *,
        high_risk_threshold: float = 0.70,
        reject_risk_threshold: float = 0.90,
    ) -> RemediationRiskAssessment:
        signals: list[RemediationRiskSignal] = []
        components: dict[str, float] = {
            "permission_expansion": 0.0,
            "wildcard_access": 0.0,
            "multi_file": 0.0,
            "rollback_uncertainty": 0.0,
            "secret_exposure": 0.0,
        }

        proposed_parts: list[str] = []
        for change in candidate.changes or []:
            text = f"{change.proposed_fragment or ''}\n{change.original_fragment or ''}"
            proposed_parts.append(text)
            if contains_wildcard(change.proposed_fragment):
                components["wildcard_access"] = max(components["wildcard_access"], 0.95)
                signals.append(
                    RemediationRiskSignal(
                        risk_type=RemediationRiskType.WILDCARD_ACCESS,
                        severity=ConstraintSeverity.BLOCKING,
                        description="Proposed fragment contains wildcard access",
                        affected_artifact=change.artifact_id,
                    )
                )
            if change.change_type and "PERMISSION" in str(change.change_type).upper():
                # Narrow single-action add is low; expansion without resource scope is higher.
                proposed = change.proposed_fragment or ""
                if contains_wildcard(proposed) or "AdministratorAccess" in proposed:
                    components["permission_expansion"] = max(
                        components["permission_expansion"], 0.95
                    )
                else:
                    components["permission_expansion"] = max(
                        components["permission_expansion"], 0.25
                    )
                    signals.append(
                        RemediationRiskSignal(
                            risk_type=RemediationRiskType.PERMISSION_EXPANSION,
                            severity=ConstraintSeverity.LOW,
                            description="Narrow permission addition",
                            affected_artifact=change.artifact_id,
                            mitigation="scope_exact_resource",
                        )
                    )

        files = {c.source_path for c in (candidate.changes or []) if c.source_path}
        if candidate.changed_file_count > 1 or len(files) > 1:
            components["multi_file"] = 0.4
            signals.append(
                RemediationRiskSignal(
                    risk_type=RemediationRiskType.MULTI_FILE_CHANGE,
                    severity=ConstraintSeverity.MEDIUM,
                    description="Candidate touches multiple files",
                )
            )

        rollback = candidate.rollback_plan
        if not rollback or (isinstance(rollback, dict) and not rollback.get("rollback_steps")):
            components["rollback_uncertainty"] = 0.35
            signals.append(
                RemediationRiskSignal(
                    risk_type=RemediationRiskType.ROLLBACK_UNCERTAINTY,
                    severity=ConstraintSeverity.MEDIUM,
                    description="Rollback plan incomplete",
                )
            )

        score = min(1.0, max(components.values()) if components else 0.0)
        # Blend lightly with mean of non-zero components.
        nonzero = [v for v in components.values() if v > 0]
        if nonzero:
            score = min(1.0, 0.7 * max(nonzero) + 0.3 * (sum(nonzero) / len(nonzero)))

        if score >= reject_risk_threshold or components["wildcard_access"] >= 0.9:
            level = RiskLevel.CRITICAL
        elif score >= high_risk_threshold:
            level = RiskLevel.HIGH
        elif score >= 0.35:
            level = RiskLevel.MEDIUM
        elif score > 0:
            level = RiskLevel.LOW
        else:
            level = RiskLevel.LOW

        blocking = [
            s.description
            for s in signals
            if str(getattr(s.severity, "value", s.severity)) in {"BLOCKING", "HIGH"}
            or s.risk_type == RemediationRiskType.WILDCARD_ACCESS
        ]

        return RemediationRiskAssessment(
            overall_risk_score=round(score, 4),
            risk_level=level,
            component_scores=components,
            risk_signals=signals,
            blocking_risks=blocking,
        )
