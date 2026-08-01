"""Phase 6A.6 Part 2 — candidate prioritiser (verification order only)."""

from __future__ import annotations

from app.domain.counterfactual_remediation.generation_enums import (
    BlastRadiusLevel,
    CandidatePriorityStatus,
    RiskLevel,
)
from app.domain.counterfactual_remediation.generation_models import (
    PrioritisationResult,
    RemediationCandidateQualityAssessment,
)
from app.domain.counterfactual_remediation.generation_versions import (
    REMEDIATION_CANDIDATE_PRIORITISER_VERSION,
)
from app.domain.counterfactual_remediation.models import CounterfactualRemediationCandidate


def contains_broad(candidate: CounterfactualRemediationCandidate) -> bool:
    for change in candidate.changes or []:
        text = change.proposed_fragment or ""
        if "*" in text or "AdministratorAccess" in text:
            return True
    return False


class RemediationCandidatePrioritiser:
    """Order unverified candidates for later verification — never 'the fix'."""

    version = REMEDIATION_CANDIDATE_PRIORITISER_VERSION

    def prioritise(
        self,
        candidates: list[CounterfactualRemediationCandidate],
        *,
        high_risk_threshold: float = 0.70,
        reject_risk_threshold: float = 0.90,
        tie_epsilon: float = 0.02,
    ) -> PrioritisationResult:
        if not candidates:
            return PrioritisationResult(
                ordered_candidate_ids=[],
                priority_statuses={},
                quality_assessments=[],
                selected_for_verification=[],
                no_safe_candidate=True,
                warnings=["no_candidates"],
                version=self.version,
            )

        scored: list[tuple[float, CounterfactualRemediationCandidate, dict[str, float]]] = []
        for candidate in candidates:
            components = self._quality_components(candidate)
            score = self._score_from_components(components)
            ctypes = {str(t).upper() for t in (candidate.change_types or [])}
            if any("ROLE" in t for t in ctypes):
                score += 0.08
            if any("PERMISSION" in t for t in ctypes) and contains_broad(candidate):
                score -= 0.12
            score = max(0.0, min(1.0, score))
            scored.append((score, candidate, components))

        scored.sort(key=lambda item: (-item[0], item[1].candidate_key or item[1].id))

        statuses: dict[str, CandidatePriorityStatus | str] = {}
        ordered: list[str] = []
        assessments: list[RemediationCandidateQualityAssessment] = []
        selected: list[str] = []
        safe_count = 0
        top_score: float | None = None

        for idx, (score, candidate, components) in enumerate(scored):
            candidate.priority_score = round(score, 4)
            candidate.quality_components_json = components
            risk = float(candidate.risk_score or 0.0)
            if candidate.status and str(candidate.status).upper() in {
                "REJECTED",
                "UNSAFE",
                "INVALID",
            }:
                status = CandidatePriorityStatus.REJECTED_CANDIDATE
            elif not candidate.changes:
                status = CandidatePriorityStatus.INCOMPLETE_CANDIDATE
            elif (
                risk >= reject_risk_threshold or (candidate.risk_level or "") == RiskLevel.CRITICAL
            ):
                status = CandidatePriorityStatus.REJECTED_CANDIDATE
            elif risk >= high_risk_threshold or (candidate.risk_level or "") == RiskLevel.HIGH:
                status = CandidatePriorityStatus.HIGH_RISK_CANDIDATE
            elif idx == 0 or (
                top_score is not None and abs(score - top_score) <= tie_epsilon and safe_count == 0
            ):
                status = CandidatePriorityStatus.PRIORITY_CANDIDATE
                safe_count += 1
                top_score = score if top_score is None else top_score
                selected.append(candidate.id)
            else:
                status = CandidatePriorityStatus.ALTERNATIVE_CANDIDATE
                safe_count += 1
                selected.append(candidate.id)

            candidate.priority_status = status.value
            statuses[candidate.id] = status
            ordered.append(candidate.id)
            assessments.append(
                RemediationCandidateQualityAssessment(
                    candidate_id=candidate.id,
                    candidate_priority_score=candidate.priority_score or 0.0,
                    components=components,
                )
            )

        no_safe = safe_count == 0 or all(
            (status.value if isinstance(status, CandidatePriorityStatus) else str(status))
            in {
                CandidatePriorityStatus.REJECTED_CANDIDATE.value,
                CandidatePriorityStatus.INCOMPLETE_CANDIDATE.value,
            }
            for status in (statuses[cid] for cid in ordered)
        )
        if no_safe:
            for _score, cand, _comp in scored:
                if statuses.get(cand.id) != CandidatePriorityStatus.REJECTED_CANDIDATE:
                    statuses[cand.id] = CandidatePriorityStatus.NO_SAFE_CANDIDATE
                    cand.priority_status = CandidatePriorityStatus.NO_SAFE_CANDIDATE.value
            selected = []

        return PrioritisationResult(
            ordered_candidate_ids=ordered,
            priority_statuses=statuses,
            quality_assessments=assessments,
            selected_for_verification=selected,
            no_safe_candidate=no_safe,
            version=self.version,
        )

    def _quality_components(
        self, candidate: CounterfactualRemediationCandidate
    ) -> dict[str, float]:
        file_count = max(1, candidate.changed_file_count or 1)
        line_count = max(1, candidate.changed_line_count or 1)
        minimality = max(0.0, 1.0 - min(1.0, (file_count - 1) * 0.2 + line_count / 400.0))
        risk_penalty = float(candidate.risk_score or 0.0)
        blast = str(candidate.blast_radius or BlastRadiusLevel.UNKNOWN)
        blast_penalty = {
            BlastRadiusLevel.LOCAL.value: 0.0,
            BlastRadiusLevel.LIMITED.value: 0.1,
            BlastRadiusLevel.MODERATE.value: 0.25,
            BlastRadiusLevel.BROAD.value: 0.45,
        }.get(blast, 0.2)
        rollback_quality = 0.8 if candidate.rollback_plan else 0.2
        assumptions_penalty = min(0.4, 0.05 * len(candidate.assumptions or []))
        return {
            "minimality": round(minimality, 4),
            "locality": 1.0 if file_count <= 1 else 0.5,
            "specificity": 0.8 if candidate.primary_artifact_id else 0.3,
            "risk_penalty": round(risk_penalty, 4),
            "blast_radius_penalty": blast_penalty,
            "rollback_quality": rollback_quality,
            "assumption_penalty": round(assumptions_penalty, 4),
            "template_confidence": 0.7 if candidate.template_id else 0.4,
        }

    def _score_from_components(self, components: dict[str, float]) -> float:
        return (
            0.25 * components.get("minimality", 0)
            + 0.15 * components.get("locality", 0)
            + 0.15 * components.get("specificity", 0)
            + 0.15 * components.get("rollback_quality", 0)
            + 0.10 * components.get("template_confidence", 0)
            - 0.25 * components.get("risk_penalty", 0)
            - 0.15 * components.get("blast_radius_penalty", 0)
            - 0.10 * components.get("assumption_penalty", 0)
        )


def assess_quality(
    candidate: CounterfactualRemediationCandidate,
) -> RemediationCandidateQualityAssessment:
    prioritiser = RemediationCandidatePrioritiser()
    components = prioritiser._quality_components(candidate)
    score = max(0.0, min(1.0, prioritiser._score_from_components(components)))
    return RemediationCandidateQualityAssessment(
        candidate_id=candidate.id,
        components=components,
        candidate_priority_score=round(score, 4),
    )
