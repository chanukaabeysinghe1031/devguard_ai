"""Hypothesis contradiction analysis (candidates only — not disproof)."""

from __future__ import annotations

from app.ai.evidence_assessment.versions import CONTRADICTION_ANALYSIS_VERSION
from app.domain.evidence_assessment.enums import EvidenceAssessmentType
from app.domain.evidence_assessment.models import (
    EvidenceAssessment,
    HypothesisContradictionAssessment,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class HypothesisContradictionAnalyzer:
    """Derive contradiction candidates and a ranking penalty in [0, 1]."""

    def analyze(
        self,
        *,
        hypothesis_id: str,
        assessments: list[EvidenceAssessment],
    ) -> HypothesisContradictionAssessment:
        contradict_items = [
            a
            for a in assessments
            if a.assessment_type == EvidenceAssessmentType.CONTRADICTION_CANDIDATE
        ]
        warnings: list[str] = []
        if contradict_items:
            warnings.append("contradiction_candidates_present")

        if contradict_items:
            strongest = max(
                (0.6 * a.confidence + 0.4 * a.relevance_score for a in contradict_items),
                default=0.0,
            )
            mean_strength = sum(
                0.6 * a.confidence + 0.4 * a.relevance_score for a in contradict_items
            ) / len(contradict_items)
            # Penalty grows with strength and count, capped.
            count_factor = min(1.0, 0.35 + 0.20 * (len(contradict_items) - 1))
            penalty = _clamp(0.70 * mean_strength + 0.30 * strongest) * count_factor
        else:
            strongest = 0.0
            mean_strength = 0.0
            penalty = 0.0

        return HypothesisContradictionAssessment(
            hypothesis_id=hypothesis_id,
            contradiction_penalty=_clamp(penalty),
            contradiction_item_count=len(contradict_items),
            contradiction_candidate_ids=sorted(a.item_id for a in contradict_items),
            strongest_contradiction_score=_clamp(strongest),
            component_scores={
                "mean_contradiction_strength": _clamp(mean_strength),
                "strongest_contradiction": _clamp(strongest),
                "count_factor": min(1.0, len(contradict_items) / 3.0) if contradict_items else 0.0,
            },
            warnings=warnings,
            analyzer_version=CONTRADICTION_ANALYSIS_VERSION,
        )
